from pathlib import Path


def test_readiness_workflow_runs_full_ci_and_true_contract_acceptance():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / '.github/workflows/production-readiness.yml').read_text()
    assert 'pull_request:' in workflow
    assert 'workflow_dispatch:' in workflow
    assert 'codex/helpdesk-production-readiness-v1' in workflow
    assert 'python scripts/run_ci_suite.py --workspace' in workflow
    assert '--layer' not in workflow
    assert 'postgres:16' in workflow
    assert 'uses: ./.github/workflows/endpoint-contract-acceptance.yml' in workflow
    assert 'needs: [full-ci, endpoint-contract]' in workflow
    assert 'helpdesk-full-ci-${{ github.sha }}' in workflow
