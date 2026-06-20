"""HexaArch CLI — stdlib argparse (typer 의존 없이 동작). (DESIGN §11 CLI 계약 일부)

명령:
  validate <spec>                스펙 검증만 (§16.5) — 깨진 IR이면 종료코드 2
  scaffold <spec> <out>          스펙 → §3 골격 생성 (결정론적)
  check    <spec> <project>      생성 프로젝트가 골격/경계를 깼는지 판정 — 위반이면 종료코드 3
  gate     <old> <new>           스펙 변경(old→new)의 충돌 판정 (§10)
                                   — 대안 필요 시 종료코드 4, 거부 시 5
  extract  <policy> <out>         정책문서 → 스펙 초안 (LLM, 사용자 Claude 세션)
                                   — 추출→검증→복구 루프, 실패 시 종료코드 6
  select-arch <policy>            정책문서 → 아키텍처 대안 N개 (LLM, 자문). 실패 시 종료코드 6

종료코드: 0 통과 · 2 스펙 검증 실패 · 3 check 위반 · 4 gate 대안 · 5 gate 거부 · 6 LLM 실패.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from hexaarch.check import check
from hexaarch.gate import gate
from hexaarch.scaffold import scaffold
from hexaarch.spec import load_spec


def _load(path: str):
    try:
        return load_spec(path), None
    except Exception as e:  # noqa: BLE001
        return None, f"스펙 검증 실패 ({path}): {e}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hexaarch",
        description="Policy-Driven Hexagonal Scaffolding Framework",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_val = sub.add_parser("validate", help="스펙 검증 (깨진 IR 거부)")
    p_val.add_argument("spec")

    p_scaf = sub.add_parser("scaffold", help="스펙 → 골격 생성 (결정론적)")
    p_scaf.add_argument("spec")
    p_scaf.add_argument("out")

    p_chk = sub.add_parser("check", help="생성 프로젝트의 골격/경계 위반 판정")
    p_chk.add_argument("spec")
    p_chk.add_argument("project")

    p_gate = sub.add_parser("gate", help="스펙 변경(old→new)의 충돌 판정")
    p_gate.add_argument("old", help="현재(기준) 스펙")
    p_gate.add_argument("new", help="제안된 스펙")
    p_gate.add_argument("--allow-breaking", action="store_true",
                        help="거부(reject)를 명시 결재로 통과시킴 (마이그레이션 완료 가정)")

    p_ext = sub.add_parser("extract", help="정책문서 → 스펙 초안 (LLM, 사용자 Claude 세션)")
    p_ext.add_argument("policy")
    p_ext.add_argument("out")
    p_ext.add_argument("--model", default=None, help="claude 모델 별칭/이름 (예: sonnet)")
    p_ext.add_argument("--max-repair", type=int, default=2, help="검증 실패 시 자가복구 재시도 횟수")

    p_arch = sub.add_parser("select-arch", help="정책문서 → 아키텍처 대안 N개 (LLM, 자문)")
    p_arch.add_argument("policy")
    p_arch.add_argument("--n", type=int, default=3, help="제시할 대안 수")
    p_arch.add_argument("--model", default=None, help="claude 모델 별칭/이름")
    p_arch.add_argument("--out", default=None, help="대안을 JSON으로 저장할 경로(선택)")

    args = parser.parse_args(argv)

    if args.cmd == "extract":
        return _run_extract(args)
    if args.cmd == "select-arch":
        return _run_select_arch(args)

    if args.cmd == "gate":
        old, err = _load(args.old)
        new, err2 = _load(args.new)
        if err or err2:
            print(err or err2, file=sys.stderr)
            return 2
        return _run_gate(old, new, args.allow_breaking)

    spec, err = _load(args.spec)
    if err:
        print(err, file=sys.stderr)
        return 2

    if args.cmd == "validate":
        print(f"OK — {len(spec.contexts)}개 컨텍스트, 검증 통과")
        return 0
    if args.cmd == "scaffold":
        files = scaffold(spec, args.out)
        print(f"생성 완료 — {len(files)}개 파일 → {args.out}")
        return 0
    if args.cmd == "check":
        report = check(spec, args.project)
        if report.ok:
            print(f"✓ check 통과 — 골격 {report.checked_files}개 파일, 위반 0")
            return 0
        print(f"✗ check 실패 — 위반 {len(report.violations)}건 / 골격 {report.checked_files}개 파일",
              file=sys.stderr)
        for v in report.violations:
            print(str(v), file=sys.stderr)
        return 3
    return 1


def _run_extract(args) -> int:
    from hexaarch.extract import extract, spec_to_yaml
    from hexaarch.llm import ClaudeSessionBackend, LLMError

    policy = pathlib.Path(args.policy)
    if not policy.exists():
        print(f"정책문서 없음: {policy}", file=sys.stderr)
        return 6
    backend = ClaudeSessionBackend()
    print(f"정책문서 추출 중 (사용자 Claude 세션)… {policy}", file=sys.stderr)
    try:
        spec = extract(policy.read_text(encoding="utf-8"), backend,
                       model=args.model, max_repair=args.max_repair)
    except LLMError as e:
        print(f"extract 실패: {e}", file=sys.stderr)
        return 6
    pathlib.Path(args.out).write_text(spec_to_yaml(spec), encoding="utf-8")
    aggs = sum(len(c.domains) for c in spec.contexts)
    print(f"✓ extract 완료 — {len(spec.contexts)}개 컨텍스트 · {aggs}개 도메인 → {args.out}")
    print("  (검증 통과한 초안. scaffold 전에 사람이 한 번 검토 권장.)")
    return 0


def _run_select_arch(args) -> int:
    from hexaarch.llm import ClaudeSessionBackend, LLMError
    from hexaarch.select_arch import render_text, select_arch

    policy = pathlib.Path(args.policy)
    if not policy.exists():
        print(f"정책문서 없음: {policy}", file=sys.stderr)
        return 6
    print(f"아키텍처 대안 탐색 중 (사용자 Claude 세션)… {policy}", file=sys.stderr)
    try:
        proposal = select_arch(policy.read_text(encoding="utf-8"),
                               ClaudeSessionBackend(), n=args.n, model=args.model)
    except LLMError as e:
        print(f"select-arch 실패: {e}", file=sys.stderr)
        return 6
    print(render_text(proposal))
    if args.out:
        pathlib.Path(args.out).write_text(
            proposal.model_dump_json(indent=2), encoding="utf-8")
        print(f"\n(대안 {len(proposal.alternatives)}개 저장 → {args.out})", file=sys.stderr)
    return 0


def _run_gate(old, new, allow_breaking: bool) -> int:
    report = gate(old, new)
    c = report.counts()
    if not report.changes:
        print("✓ gate — 스펙 변경 없음")
        return 0
    verdict = report.verdict
    out = sys.stdout if verdict == "pass" else sys.stderr
    label = {"pass": "통과", "review": "대안 필요", "reject": "거부"}[verdict]
    print(f"gate 판정: {label}  (통과 {c['pass']} · 대안 {c['review']} · 거부 {c['reject']})",
          file=out)
    for ch in report.changes:
        print(str(ch), file=out)
    if verdict == "reject":
        if allow_breaking:
            print("\n--allow-breaking: 거부 변경을 명시 결재로 통과 처리.", file=sys.stderr)
            return 0
        print("\n거부된 변경이 있다. 마이그레이션 후 --allow-breaking으로만 통과 가능.",
              file=sys.stderr)
        return 5
    if verdict == "review":
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
