import os
import tempfile
import unittest
from pathlib import Path

from app.project_intake import build_initial_documents


class ProfessionalDocumentTests(unittest.TestCase):
    def test_initial_documents_have_delivery_grade_structure(self):
        docs = build_initial_documents({
            "name": "HMI MES Mini Line",
            "project_type": "manufacturing_automation",
            "goal": "PLC 생산 데이터를 수집해 HMI와 MES에서 실시간 확인한다.",
            "problem": "수기 생산 기록 때문에 실적 집계와 이상 추적이 늦다.",
            "users": "생산 작업자, 설비 담당자, 품질 담당자",
            "deliverables": "PLC 연동, HMI, 생산실적 DB, 운영 가이드, QA 결과",
            "success_criteria": "생산수량/불량수량/설비상태를 실시간 표시하고 테스트 시나리오를 통과한다.",
            "scope": "포함=시뮬레이터, Python Gateway, Web HMI, SQLite / 제외=ERP",
            "constraints": "V1은 Windows Local과 PLC Simulator를 우선 사용한다.",
        })
        self.assertIn("Executive Summary", docs["proposal"])
        self.assertIn("승인 기준", docs["proposal"])
        self.assertIn("Work Breakdown Structure", docs["plan"])
        self.assertIn("변경관리", docs["plan"])
        self.assertIn("Acceptance Criteria", docs["requirements"])
        self.assertIn("Traceability Matrix", docs["requirements"])
        self.assertIn("Exit Criteria", docs["milestone"])
        self.assertIn("Definition of Done", docs["backlog"])

    def test_web_workspace_is_read_first_and_printable(self):
        js = Path("app/static/app.js").read_text(encoding="utf-8")
        css = Path("app/static/styles.css").read_text(encoding="utf-8")
        self.assertIn("function renderMarkdownDocument", js)
        self.assertIn("문서 보기", js)
        self.assertIn("Markdown 편집", js)
        self.assertIn("print-document", js)
        self.assertIn("professional-document", css)
        self.assertIn("@media print", css)


if __name__ == "__main__":
    unittest.main()
