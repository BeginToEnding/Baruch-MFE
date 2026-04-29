from __future__ import annotations
import re
from pathlib import Path
from typing import List, Dict, Tuple, Iterator, Optional
from src.utils import read_text

SECTION_HEADERS = {
    "Presentation Operator Message",
    "Presenter Speech",
    "Question and Answer Operator Message",
    "Question",
    "Answer",
}

ROLE_LINE_RE = re.compile(r"^(Executives|Analysts|Operator)\b.*$")

HEADER_RE = re.compile(
    r"^(?P<company>.+?),\s*Q(?P<q>\d)\s*(?P<y>\d{4}).*?Earnings Call.*?(?P<date>[A-Z][a-z]+ \d{1,2},\s*\d{4})",
    re.MULTILINE,
)


class TranscriptParser:
    def __init__(self, dedupe_repeated_blocks: bool = True, min_body_chars_for_dedupe: int = 20):
        self.dedupe_repeated_blocks = dedupe_repeated_blocks
        self.min_body_chars_for_dedupe = min_body_chars_for_dedupe

    def _clean_text_field(self, s: str) -> str:
        """
        Remove BOM and surrounding whitespace from text fields.
        """
        return (s or "").replace("\ufeff", "").strip()

    def _filename_meta(self, path: Path) -> Tuple[str, str]:
        stem = path.stem
        ticker, _, q = stem.partition("_")
        return self._clean_text_field(ticker), self._clean_text_field(q)

    def parse_header(self, text: str) -> dict:
        text = text.replace("\ufeff", "")
        m = HEADER_RE.search(text)
        if not m:
            return {"company": "", "quarter": "", "call_date": None}

        quarter = f"Q{m.group('q')}-{m.group('y')}"
        call_date = self._clean_text_field(m.group("date"))

        return {
            "company": self._clean_text_field(m.group("company")),
            "quarter": self._clean_text_field(quarter),
            "call_date": call_date,
        }

    def _clean_role_line(self, role_line: str) -> str:
        s = self._clean_text_field(role_line)
        if not s:
            return ""

        s = re.sub(r"\s*-\s*nan\s*$", "", s, flags=re.IGNORECASE).strip()

        if s in {"Executives", "Analysts", "Operator"}:
            return s

        return s

    def _normalize_for_dedupe(self, text: str) -> str:
        text = self._clean_text_field(text).lower()
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[“”]", '"', text)
        text = re.sub(r"[‘’]", "'", text)
        return text

    def _is_near_duplicate_block(
        self,
        prev_section: str,
        prev_role: str,
        prev_body: str,
        cur_section: str,
        cur_role: str,
        cur_body: str,
    ) -> bool:
        if prev_section != cur_section:
            return False
        if (prev_role or "").strip() != (cur_role or "").strip():
            return False

        prev_norm = self._normalize_for_dedupe(prev_body)
        cur_norm = self._normalize_for_dedupe(cur_body)

        if not prev_norm or not cur_norm:
            return False

        if min(len(prev_norm), len(cur_norm)) < self.min_body_chars_for_dedupe:
            return False

        if prev_norm == cur_norm:
            return True

        shorter_len = min(len(prev_norm), len(cur_norm))
        longer_len = max(len(prev_norm), len(cur_norm))
        if shorter_len / longer_len >= 0.95:
            if prev_norm in cur_norm or cur_norm in prev_norm:
                return True

        return False

    def _blocks(self, text: str) -> Iterator[Tuple[str, str, str]]:
        text = text.replace("\ufeff", "")
        lines = text.splitlines()
        i, n = 0, len(lines)

        prev_emitted: Optional[Tuple[str, str, str]] = None

        while i < n:
            line = self._clean_text_field(lines[i])
            if line in SECTION_HEADERS:
                section = line
                i += 1

                while i < n and not self._clean_text_field(lines[i]):
                    i += 1

                role_line = ""
                if i < n and ROLE_LINE_RE.match(self._clean_text_field(lines[i])):
                    role_line = self._clean_role_line(lines[i])
                    i += 1

                body = []
                while i < n and self._clean_text_field(lines[i]) not in SECTION_HEADERS:
                    body.append(lines[i])
                    i += 1

                body_text = self._clean_text_field("\n".join(body))

                if not body_text and not role_line:
                    continue

                current = (section, role_line, body_text)

                if self.dedupe_repeated_blocks and prev_emitted is not None:
                    if self._is_near_duplicate_block(
                        prev_section=prev_emitted[0],
                        prev_role=prev_emitted[1],
                        prev_body=prev_emitted[2],
                        cur_section=current[0],
                        cur_role=current[1],
                        cur_body=current[2],
                    ):
                        continue

                prev_emitted = current
                yield current
            else:
                i += 1

    def extract_prepared_blocks(self, text: str) -> List[Dict]:
        prepared = []
        for section, role_line, body in self._blocks(text):
            if section == "Presenter Speech" and body:
                prepared.append({"role": role_line, "text": body})
        return prepared

    def extract_qa_pairs(self, text: str) -> List[Dict]:
        qa = []
        pending_q = None

        def flush_pending():
            nonlocal pending_q, qa
            if pending_q is not None:
                qa.append(pending_q)
                pending_q = None

        for section, role_line, body in self._blocks(text):
            if section == "Question":
                flush_pending()
                pending_q = {
                    "q_role": role_line,
                    "question": body,
                    "answers": [],
                }

            elif section == "Answer":
                if pending_q is None:
                    qa.append(
                        {
                            "q_role": "",
                            "question": "",
                            "answers": [{"a_role": role_line, "answer": body}],
                        }
                    )
                else:
                    pending_q["answers"].append(
                        {"a_role": role_line, "answer": body}
                    )

        flush_pending()
        return qa

    def parse_file(self, path: str | Path) -> dict:
        path = Path(path)
        text = read_text(path).replace("\ufeff", "")
        ticker, quarter_from_name = self._filename_meta(path)
        header = self.parse_header(text)
        quarter = header["quarter"] or quarter_from_name

        return {
            "ticker": self._clean_text_field(ticker),
            "quarter": self._clean_text_field(quarter),
            "company": self._clean_text_field(header["company"]),
            "call_date": self._clean_text_field(header["call_date"]) if header["call_date"] else None,
            "prepared_blocks": self.extract_prepared_blocks(text),
            "qa_pairs": self.extract_qa_pairs(text),
            "raw_path": str(path),
        }

def transcript_to_prompt_text(record: dict, max_chars: int = 100000) -> str:
    prepared_chunks = []
    for b in record.get("prepared_blocks", []):
        prepared_chunks.append(f"[PREPARED | {b.get('role','')}]\n{b.get('text','')}")
    qa_chunks = []
    for pair in record.get("qa_pairs", []):
        qa_chunks.append(
            f"[QUESTION | {pair.get('q_role','')}]\n{pair.get('question','')}\n"
            f"[ANSWER | {pair.get('a_role','')}]\n{pair.get('answer','')}"
        )
    text = "\n\n".join([
        f"Ticker: {record.get('ticker','')}",
        f"Quarter: {record.get('quarter','')}",
        f"Call date: {record.get('call_date','')}",
        "=== PREPARED REMARKS ===",
        "\n\n".join(prepared_chunks),
        "=== Q&A ===",
        "\n\n".join(qa_chunks),
    ])
    return text[:max_chars]
