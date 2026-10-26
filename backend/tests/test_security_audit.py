from tools.security_audit import audit, inventory, secret_scan


def test_sec08_dependency_scan_fails_incomplete_and_preserves_advisory_ids():
    calls = []
    def query(batch):
        calls.extend(batch)
        return [{"vulns": [{"id": "DEMO-advisory"}]} if i == 0 else {} for i, _ in enumerate(batch)]
    result = audit(True, query)
    assert result["status"] == "complete" and result["queried"] == len(calls)
    assert result["findings"][0]["advisories"] == ["DEMO-advisory"]
    def failed(batch):
        raise TimeoutError("DEMO-secret-network-error")
    partial = audit(True, failed)
    assert partial["status"] == "incomplete" and partial["queried"] == 0
    assert all(row["exception_class"] == "TimeoutError" for row in partial["errors"])
    assert "DEMO-secret" not in str(partial)
    assert all(set(row) == {"package", "version"} for row in inventory())


def test_sec09_secret_scanner_reports_location_without_value(tmp_path):
    canary = "sk-" + "x" * 32
    (tmp_path / "app.py").write_text('key="' + canary + '"')
    (tmp_path / ".env").write_text('key="' + canary + '"')
    result = secret_scan(tmp_path)
    assert result["files_scanned"] == 1 and result["findings"] == [{"file": "app.py", "line": 1, "rule": "provider_token"}]
    assert canary not in str(result)
