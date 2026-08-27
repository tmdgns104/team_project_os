const assert = require('assert');
const Gantt = require('../app/static/milestone_gantt.js');

const md = `# 개발 마일스톤

> **기준 시작일** · 2026-09-01

## Gantt Schedule

| Phase | ID | Task | Start Week | End Week | Owner | Status |
|---|---|---|---|---|---|---|
| A. 분석 및 설계 | MS-001 | 프로젝트 착수 | 1 | 1 | PM | Done |
| A. 분석 및 설계 | MS-002 | 요구사항 분석 및 정의 | 1 | 2 | PM | In Progress |
| B. 구현 | MS-003 | Backend 개발 | 4 | 8 | Dev | Todo |
| B. 구현 | MS-004 | HMI 개발 | 6 | 10 | Dev | Review |
| C. 통합/테스트 | MS-005 | 통합 테스트 | 11 | 14 | QA | Draft |
`;

const parsed = Gantt.parse(md);
assert.equal(parsed.rows.length, 5);
assert.equal(parsed.rows[1].start, 1);
assert.equal(parsed.rows[1].end, 2);
assert.equal(parsed.weeks, 16);
assert.equal(parsed.startDate, '2026-09-01');

for (let i=0;i<parsed.rows.length;i++) {
  for (let j=i+1;j<parsed.rows.length;j++) {
    // Tasks may overlap in time by design, but table rows must remain separate records.
    assert.notStrictEqual(parsed.rows[i], parsed.rows[j]);
  }
}

const html = Gantt.render(md, '마일스톤', 'Factory HMI/MES');
assert(html.includes('DEVELOPMENT MILESTONE'));
assert(html.includes('1 month'));
assert(html.includes('16W'));
assert(html.includes('rowspan="2"'));
assert(html.includes('status-done'));
assert(html.includes('status-in_progress'));
assert(html.includes('Backend 개발'));
assert(!html.includes('<script>alert'));

const legacy = `# 마일스톤\n\n| ID | Milestone | 목표 | 상태 |\n|---|---|---|---|\n| M1 | Definition Baseline | 요구사항 기준선 | Draft |\n| M2 | Design Baseline | 설계 기준선 | Draft |`;
const legacyParsed = Gantt.parse(legacy);
assert.equal(legacyParsed.rows.length, 2);
assert.equal(legacyParsed.inferred, true);
assert.equal(legacyParsed.rows[0].start, 1);
assert.equal(legacyParsed.rows[1].start, 5);

console.log('Milestone Gantt tests: PASS');
