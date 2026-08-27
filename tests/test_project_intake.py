import unittest

from app.project_intake import build_initial_documents, evaluate_intake, intake_metadata


class UniversalProjectIntakeSimulationTests(unittest.TestCase):
    def detailed_case(self, project_type: str):
        return {
            "project_type": project_type,
            "name": "범용 프로젝트 시뮬레이션",
            "goal": "현재 수작업 중심의 업무를 표준화하고 반복 작업을 줄여 담당자가 결과와 상태를 쉽게 확인할 수 있게 한다.",
            "problem": "현재 담당자마다 처리 방식이 달라 누락과 재작업이 발생하고, 진행 상태를 한 곳에서 확인할 수 없어 의사결정이 늦어진다.",
            "users": "직접 사용자=실무 담당자, 결과 확인=팀장, 운영=관리자, 최종 승인=프로젝트 책임자",
            "deliverables": "실행 가능한 결과물, 운영 절차, 사용자 가이드, 검증 결과서, 인수 기준 문서",
            "success_criteria": "핵심 업무 처리시간 30% 이상 단축, 주요 오류 50% 이상 감소, 인수 테스트 95% 이상 통과",
            "scope": "포함=핵심 업무 흐름과 검증, 사용자 가이드 / 제외=전사 시스템 전체 교체와 범위 밖 조직 프로세스",
            "current_state": "담당자가 개별 도구와 문서로 처리하고 결과를 수동 취합한다.",
            "target_state": "표준 흐름에 따라 작업하고 상태와 결과가 공용 공간에 자동 집계된다.",
            "constraints": "3개월 내 완료, 기존 장비와 데이터 유지, 예산 범위 준수, 외부 반출 금지 데이터 보호",
            "schedule": "1개월차 기획/검증기준, 2개월차 구현/적용, 3개월차 통합검증/인수",
            "team": "PM 1, 실무 담당 2, 구현 담당 2, 검증 담당 1, 승인자 1",
            "risks": "현행 절차가 문서화되지 않았고 기존 데이터 품질 편차가 있을 수 있음",
            "description": "기존 자산은 가능한 재사용하고 변경사항은 팀 합의 후 반영한다.",
        }

    def test_detailed_inputs_score_high_across_project_types(self):
        project_types = [
            "software",
            "ai_data",
            "embedded_hardware",
            "manufacturing_automation",
            "research_rnd",
            "business_process",
            "product_service",
            "education_content",
            "event_campaign",
            "generic",
        ]
        for project_type in project_types:
            with self.subTest(project_type=project_type):
                result = evaluate_intake(self.detailed_case(project_type))
                self.assertGreaterEqual(result["score"], 85)
                self.assertEqual(result["level"], "excellent")
                self.assertTrue(result["type_questions"])

    def test_vague_input_is_flagged_before_document_generation(self):
        vague = {
            "project_type": "generic",
            "name": "새 프로젝트",
            "goal": "좋게 만들기",
            "problem": "불편함",
            "users": "사람들",
            "deliverables": "결과물",
            "success_criteria": "잘 되면 됨",
            "scope": "전부",
            "constraints": "없음",
        }
        result = evaluate_intake(vague)
        self.assertLess(result["score"], 50)
        self.assertEqual(result["level"], "insufficient")
        self.assertGreaterEqual(len(result["feedback"]), 4)

    def test_initial_documents_are_domain_neutral_and_use_input(self):
        case = self.detailed_case("research_rnd")
        docs = build_initial_documents(case)
        self.assertIn("연구개발 / 실험 / PoC", docs["proposal"])
        self.assertIn(case["success_criteria"], docs["proposal"])
        self.assertIn(case["constraints"], docs["plan"])
        self.assertIn("REQ-001", docs["requirements"])
        self.assertIn("M1", docs["milestone"])
        self.assertIn("프로젝트 유형별 확인 질문", docs["backlog"])

    def test_metadata_has_generic_fallback_and_multiple_domains(self):
        meta = intake_metadata()
        values = {x["value"] for x in meta["project_types"]}
        self.assertIn("generic", values)
        self.assertIn("manufacturing_automation", values)
        self.assertIn("education_content", values)
        self.assertIn("deliverables", meta["required"])
        self.assertIn("risks", meta["recommended"])


if __name__ == "__main__":
    unittest.main()
