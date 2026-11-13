Extracted 2026-11-05 from JacLLM-revdev-wave2 dataset/sft/revdev/accepted-dedup/train.jsonl:
student_system.md and tools.json from row fp=/home/imrui/Documents/Jaseci/JacLLM/JacLLM/dataset/raw/revdev/A2Pulse/runs/claude_teacher_markdown_modules_jac036_v1b#segment0 (stage revdev_app), plan_system.md from fp=/home/imrui/Documents/Jaseci/JacLLM/JacLLM/dataset/raw/revdev/A2Pulse/runs/claude_teacher_markdown_modules_jac036_v1b (stage revdev_plan).
tools.json drops load_jac_skill: the student gets no skill files in this spike (only the teacher does).
lookup_tools.json (2026-11-06): list_files, grep_search, find_symbol, analyze_project, verbatim from the prod tool schemas
(dataset/raw/prod/tools_f14d1f1.json, "MainAgent.respond"), the ones 1105 saw in prod-64k. The harness implements them
in workspace.py and lookup.jac with JacCoder's output wording.
delete_tool.json (2026-11-07): delete_code, verbatim from the same prod schemas; workspace.py answers in JacCoder's
delete_file wording. Added so the student can remove the scratch files it writes to try things.
