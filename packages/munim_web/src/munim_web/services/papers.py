"""Papers: upload, store, read in the background and repair (docs/API.md, AI_SPEC 6 and 7).

Files are stored under data/uploads/<case>/<paper>/ with generated names. The original is kept
as uploaded; the derived image (oriented, rotated, resized JPEG without metadata) is what the
viewer shows and what the model reads, so boxes and crops refer to it (D9).
Reads run one at a time (a semaphore) as asyncio tasks, and every state change is saved.
"""

from __future__ import annotations

import asyncio
import hashlib
import shutil
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal, cast

import structlog

from munim_ai import imageprep
from munim_ai.extract import extract_paper
from munim_ai.prompts import extraction_prompt
from munim_ai.providers import Provider, ProviderError, ReadContext, make_provider
from munim_ai.repair import RepairOutcome, repair_field
from munim_ai.schemas import PAPER_FIELDS, PaperKind
from munim_core.verify.models import FieldRef, Status
from munim_core.verify.registry import run_all
from munim_web.db import Database, new_id
from munim_web.services.case_service import load_case, ref_of
from munim_web.settings import Settings

__all__ = ["PROVIDERS", "PaperService", "UploadError"]

log = structlog.get_logger("munim.papers")
PROVIDERS = ("ollama", "gemini", "replay")
EXTENSIONS = {"jpeg": "jpg", "png": "png", "webp": "webp", "heic": "heic", "pdf": "pdf"}
AUTO_REPAIR = frozenset(
    {"supplier_gstin", "buyer_gstin", "invoice_total", "taxable_total", "igst", "cgst", "sgst"}
)


class UploadError(Exception):
    def __init__(self, message_key: str) -> None:
        super().__init__(message_key)
        self.message_key = message_key


@dataclass(frozen=True)
class ProviderChoice:
    name: str
    pinned: bool
    consent: bool


class PaperService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self._lock = asyncio.Semaphore(1)
        self._tasks: set[asyncio.Task[None]] = set()
        self._provider_override: Provider | None = None

    # ------------------------------------------------------------ provider (D12)
    def choice(self) -> ProviderChoice:
        consent = self.db.setting("cloud_consent") == "on"
        if self.settings.provider:
            return ProviderChoice(self.settings.provider, True, consent)
        name = self.db.setting("provider") or "ollama"
        if name == "gemini" and not consent:
            name = "ollama"
        return ProviderChoice(name, False, consent)

    def provider(self) -> Provider:
        if self._provider_override is not None:
            return self._provider_override
        choice = self.choice()
        if choice.name == "gemini" and not choice.consent:
            raise ProviderError("hosted reader without consent")
        return make_provider(
            choice.name,
            ollama_url=self.settings.ollama_url,
            ollama_model=self.db.setting("ollama_model") or self.settings.ollama_model,
            gemini_model=self.settings.gemini_model,
            gemini_key=self.settings.gemini_api_key,
            replay_dir=self.settings.replay_dir,
            use_json_format=self.settings.ollama_json_format,
        )

    def use_provider(self, provider: Provider | None) -> None:
        """Tests swap in a fake reader here."""
        self._provider_override = provider

    # ------------------------------------------------------------ files
    def folder(self, case_id: str, paper_id: str) -> Path:
        return self.settings.uploads / case_id / paper_id

    def path(self, relative: str) -> Path:
        return self.settings.uploads / relative

    async def add(self, case_id: str, kind: str, data: bytes) -> str:
        """Check and store an upload; one paper of each kind per case, so a new one replaces it."""
        if kind not in ("invoice", "challan", "po"):
            raise UploadError("paper.err.kind")
        if len(data) > self.settings.max_upload_bytes:
            raise UploadError("paper.err.size")
        try:
            file_type = imageprep.sniff(data)
            prepared = await asyncio.to_thread(imageprep.prepare, data, 0)
        except imageprep.ImageError as exc:
            raise UploadError(exc.message_key) from exc
        for old in self.db.papers(case_id):
            if old["kind"] == kind:
                self.delete(old["id"])
        paper_id = new_id()
        folder = self.folder(case_id, paper_id)
        folder.mkdir(parents=True, exist_ok=True)
        sha = hashlib.sha256(data).hexdigest()
        original = folder / f"original.{EXTENSIONS[file_type]}"
        original.write_bytes(data)
        (folder / "derived.jpg").write_bytes(prepared.jpeg)
        quality = imageprep.quality(prepared.jpeg)
        rel = original.relative_to(self.settings.uploads).as_posix()
        self.db.add_paper(
            case_id, paper_id, kind=kind, original=rel, sha256=sha, file_type=file_type
        )
        self.db.update_paper(
            paper_id,
            derived_path=(folder / "derived.jpg").relative_to(self.settings.uploads).as_posix(),
            width=prepared.width,
            height=prepared.height,
            dark=int(quality.dark),
            blurred=int(quality.blurred),
        )
        self.db.touch(case_id)
        self.db.event(case_id, "paper.added", paper=paper_id, kind=kind)
        log.info("paper.added", case=case_id, paper=paper_id, kind=kind, bytes=len(data))
        return paper_id

    def delete(self, paper_id: str) -> None:
        paper = self.db.paper(paper_id)
        if paper is None:
            return
        shutil.rmtree(self.folder(paper["case_id"], paper_id), ignore_errors=True)
        self.db.delete_paper(paper_id)
        self.db.touch(paper["case_id"])
        self.db.event(paper["case_id"], "paper.deleted", paper=paper_id)

    def delete_case_files(self, case_id: str) -> None:
        shutil.rmtree(self.settings.uploads / case_id, ignore_errors=True)

    async def rotate(self, paper_id: str, degrees: int) -> None:
        paper = self.db.paper(paper_id)
        if paper is None or paper["status"] in ("reading", "repairing"):
            return
        rotation = (int(paper["rotation"]) + degrees) % 360
        data = self.path(paper["original_path"]).read_bytes()
        prepared = await asyncio.to_thread(imageprep.prepare, data, rotation)
        self.path(paper["derived_path"]).write_bytes(prepared.jpeg)
        self.db.update_paper(
            paper_id,
            rotation=rotation,
            width=prepared.width,
            height=prepared.height,
            status="added",
        )
        self.db.replace_claims(paper_id, [])  # boxes belong to the old orientation
        self.db.touch(paper["case_id"])

    def set_kind(self, paper_id: str, kind: str) -> None:
        paper = self.db.paper(paper_id)
        if paper is None or kind not in ("invoice", "challan", "po") or paper["kind"] == kind:
            return
        for other in self.db.papers(paper["case_id"]):
            if other["kind"] == kind:
                self.delete(other["id"])
        self.db.update_paper(paper_id, kind=kind, status="added")
        self.db.replace_claims(paper_id, [])
        self.db.touch(paper["case_id"])

    # ------------------------------------------------------------ reading
    def start_read(self, paper_id: str) -> None:
        paper = self.db.paper(paper_id)
        if paper is None or paper["status"] in ("reading", "repairing"):
            return  # idempotent: a second press returns the current status
        self.db.update_paper(paper_id, status="reading", error=None)
        task = asyncio.create_task(self.read(paper_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def wait_idle(self) -> None:
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    def _hand_entry_rows(self, kind: str) -> list[dict[str, object]]:
        return [
            {"field": name, "line_index": -1, "value_read": None, "value": None, "source": "user"}
            for name in PAPER_FIELDS[kind]
        ]

    async def read(self, paper_id: str) -> None:
        async with self._lock:
            paper = self.db.paper(paper_id)
            if paper is None:
                return
            case_id, kind = paper["case_id"], cast(PaperKind, paper["kind"])
            started = time.perf_counter()
            try:
                provider = self.provider()
                derived = self.path(paper["derived_path"]).read_bytes()
                ctx = ReadContext(
                    original_sha256=paper["sha256"],
                    kind=kind,
                    prompt_version=extraction_prompt(kind).version,
                    rotation=int(paper["rotation"]),
                )
                outcome = await extract_paper(provider, derived, kind, ctx)
            except ProviderError as exc:
                self.db.replace_claims(paper_id, self._hand_entry_rows(kind))
                self.db.update_paper(paper_id, status="failed", error=exc.message_key)
                self.db.event(
                    case_id,
                    "paper.read",
                    paper=paper_id,
                    outcome="provider_error",
                    error=type(exc).__name__,
                )
                log.warning("paper.read_failed", paper=paper_id, error=type(exc).__name__)
                return
            result = outcome.result
            meta = {
                "provider": result.provider if result else provider.name,
                "model": result.model if result else provider.model,
                "prompt_version": ctx.prompt_version,
                "replayed": int(bool(result and result.replayed)),
                "read_at": date.today().isoformat(),
            }
            if not outcome.ok:
                self.db.replace_claims(paper_id, self._hand_entry_rows(kind))
                self.db.update_paper(paper_id, status="failed", error="paper.err.read", **meta)
                self.db.event(case_id, "paper.read", paper=paper_id, outcome="unreadable")
                return
            rows = [
                {
                    "field": d.field,
                    "line_index": -1 if d.index is None else d.index,
                    "value_read": d.value_read,
                    "value": d.value,
                    "box": d.box,
                    "flag": d.flag,
                }
                for d in outcome.claims
            ]
            self.db.replace_claims(paper_id, rows)
            self.db.update_paper(paper_id, status="repairing", **meta)
            self.db.touch(case_id)
            self.db.event(
                case_id,
                "paper.read",
                paper=paper_id,
                outcome="read",
                partial=int(outcome.partial),
                attempts=outcome.attempts,
            )
            log.info("paper.read", paper=paper_id, ms=round((time.perf_counter() - started) * 1000))
            try:
                await self._auto_repair(provider, case_id, paper_id)
            finally:
                self.db.update_paper(paper_id, status="read")

    async def _auto_repair(self, provider: Provider, case_id: str, paper_id: str) -> None:
        """Re-read the identifier and amount fields of this paper that a blocking rule failed."""
        snapshot = load_case(self.db, case_id, date.today())
        if snapshot is None:
            return
        for claim in [c for c in snapshot.claims if c["paper_id"] == paper_id]:
            ref = ref_of(claim)
            if ref.field not in AUTO_REPAIR or ref.index is not None:
                continue
            failing = [
                f
                for f in snapshot.findings
                if ref in f.fields and f.blocks and f.status is Status.FAILED
            ]
            if failing:
                await self.repair(claim["id"], provider=provider)

    async def repair(
        self, claim_id: str, *, provider: Provider | None = None
    ) -> RepairOutcome | None:
        """One red-pen attempt on a claim (AI_SPEC 7). Returns the outcome, or None if not run."""
        claim = self.db.claim(claim_id)
        if claim is None:
            return None
        case_id = claim["case_id"]
        snapshot = load_case(self.db, case_id, date.today())
        if snapshot is None:
            return None
        ref = ref_of(claim)
        failing_rules = {f.rule_id for f in snapshot.findings if ref in f.fields and f.blocks}
        paper = self.db.paper(claim["paper_id"])
        if paper is None or not paper["derived_path"]:
            return None
        provider = provider or self.provider()
        box = None
        if claim["box_y1"] is not None:
            box = (
                int(claim["box_y1"]),
                int(claim["box_x1"]),
                int(claim["box_y2"]),
                int(claim["box_x2"]),
            )
        kind = cast(PaperKind, paper["kind"])

        def still_failing(value: str) -> bool:
            # Re-run the rules with the proposed value and look at the rules that failed before.
            from munim_core.verify.models import CaseState, ClaimValue, PaperState

            state = snapshot.state
            current = state.papers[ref.paper_kind]
            fields = dict(current.fields)
            fields[ref.field] = ClaimValue(raw=claim["value_read"], text=value, source="repair")
            changed = CaseState(
                papers={
                    **state.papers,
                    ref.paper_kind: PaperState(current.kind, fields, current.lines),
                },
                as_on=state.as_on,
                udyam_number=state.udyam_number,
                extra=state.extra,
            )
            return any(
                f.rule_id in failing_rules
                and ref in f.fields
                and f.status in (Status.FAILED, Status.NEEDS_REVIEW)
                for f in run_all(changed, date.today())
            )

        ctx = ReadContext(
            original_sha256=paper["sha256"],
            kind=kind,
            prompt_version=extraction_prompt(kind).version,
            rotation=int(paper["rotation"]),
        )
        try:
            result = await repair_field(
                field=ref.field,
                current=claim["value_current"],
                box=box,
                attempts_so_far=int(claim["repair_attempts"]),
                provider=provider,
                prepared_image=self.path(paper["derived_path"]).read_bytes(),
                ctx=ctx,
                still_failing=still_failing,
            )
        except ProviderError as exc:
            self.db.update_claim(
                claim_id, repair_outcome="check_by_hand", repair_reason=exc.message_key
            )
            self.db.event(case_id, "claim.repair", claim=claim_id, outcome="provider_error")
            return RepairOutcome.CHECK_BY_HAND
        if result.outcome is RepairOutcome.CORRECTED and result.value is not None:
            via: Literal["lookalike", "model"] | None = result.via
            self.db.set_claim_value(
                claim_id,
                result.value,
                "repair",
                repair_via=via,
                repair_outcome=str(result.outcome),
                repair_reason=result.reason_key,
                review_flag=result.flag,
                repair_attempts=result.attempts,
                animate=1,
            )
            self.db.touch(case_id)
        else:
            self.db.update_claim(
                claim_id,
                repair_outcome=str(result.outcome),
                repair_reason=result.reason_key,
                repair_attempts=result.attempts,
                repair_via=result.via,
            )
        self.db.event(
            case_id, "claim.repair", claim=claim_id, outcome=str(result.outcome), via=result.via
        )
        return result.outcome

    def ref_versions(self, refs: list[FieldRef], case_id: str) -> dict[str, int]:
        snapshot = load_case(self.db, case_id, date.today())
        return snapshot.versions(refs) if snapshot else {}
