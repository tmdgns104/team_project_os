from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

# Update version regression.
p=ROOT/'tests/test_professional_doc_migration.py'
s=p.read_text(encoding='utf-8')
s=s.replace('def test_version_is_v012(self):','def test_version_is_v013(self):')
s=s.replace('self.assertEqual(app.version, "0.12.0")','self.assertEqual(app.version, "0.13.0")')
p.write_text(s,encoding='utf-8')

# Extend permanent CI with milestone renderer + E2E.
p=ROOT/'.github/workflows/ci.yml'
s=p.read_text(encoding='utf-8')
s=s.replace(
    'tools/simulate_live_design.py tools/simulate_project_creation_v012.py tests/test_live_design.py',
    'tools/simulate_live_design.py tools/simulate_project_creation_v012.py tools/simulate_milestone_gantt_v013.py tests/test_live_design.py'
)
needle='      - name: Diagram layout readability tests\n        run: node tests/test_diagram_layout.js\n'
insert=needle+'      - name: Milestone Gantt renderer tests\n        run: node tests/test_milestone_gantt.js\n'
if 'Milestone Gantt renderer tests' not in s:
    s=s.replace(needle,insert)
needle='      - name: Full project documents and diagrams simulator\n        run: python tools/simulate_project_creation_v012.py\n'
insert=needle+'      - name: Milestone Gantt project simulator\n        run: python tools/simulate_milestone_gantt_v013.py\n'
if 'Milestone Gantt project simulator' not in s:
    s=s.replace(needle,insert)
s=s.replace(
    '          node --check app/static/diagram_layout.js\n          node --check app/static/app.js',
    '          node --check app/static/diagram_layout.js\n          node --check app/static/milestone_gantt.js\n          node --check app/static/app.js'
)
p.write_text(s,encoding='utf-8')
print('V0.13 milestone CI integration prepared')
