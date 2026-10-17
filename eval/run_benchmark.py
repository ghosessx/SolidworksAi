"""
SolidAI Evaluation Suite — Benchmark Runner
Executes golden CAD test cases and failure injection tests against MockCADEngine or live SOLIDWORKS.
Generates a comprehensive markdown report.
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mock_engine import MockCADEngine
from cad_executor import execute_cad_plan
from cad_simulator import CADSimulator
from cad_schema import validate_cad_plan
from eval.test_cases import GOLDEN_TEST_CASES, FAILURE_INJECTION_CASES


def run_all_benchmarks(use_live_sw: bool = False) -> bool:
    print("=" * 70)
    print(" SolidAI Evaluation Benchmark Suite")
    mode = "LIVE SOLIDWORKS 2025" if use_live_sw else "HEADLESS (MockCADEngine)"
    print(f" Execution Mode: {mode}")
    print("=" * 70)

    results = []
    all_passed = True

    # 1. Golden Test Cases
    print("\n--- 1. GOLDEN MECHANICAL BENCHMARK CASES ---")
    if use_live_sw:
        from cad_engine import SolidWorksCADEngine
        engine = SolidWorksCADEngine()
    else:
        engine = MockCADEngine()

    for tc in GOLDEN_TEST_CASES:
        cid = tc["id"]
        name = tc["name"]
        plan = tc["plan"]
        exp_bodies = tc["expected_body_count"]
        min_vol = tc["expected_min_volume"]
        max_vol = tc["expected_max_volume"]

        t0 = time.time()
        engine.new_part()
        success, msg, failed_idx, state = execute_cad_plan(plan, engine, check_simulation=True)
        dur = round((time.time() - t0) * 1000, 1)

        bodies = state.get("body_count", 0)
        vol = state.get("volume_mm3", 0.0)

        # Check conditions
        body_ok = (bodies == exp_bodies)
        vol_ok = (min_vol <= vol <= max_vol)
        tc_ok = success and body_ok and vol_ok

        status_icon = "✅ PASS" if tc_ok else "❌ FAIL"
        if not tc_ok:
            all_passed = False

        print(f"[{status_icon}] {cid}: {name} ({dur} ms)")
        print(f"       Gövde: {bodies}/{exp_bodies} | Hacim: {vol:.1f} mm3 (Beklenen: {min_vol:.0f}-{max_vol:.0f})")
        if not success:
            print(f"       Hata: {msg}")

        results.append({
            "id": cid,
            "name": name,
            "status": "PASS" if tc_ok else "FAIL",
            "duration_ms": dur,
            "bodies": f"{bodies}/{exp_bodies}",
            "volume": f"{vol:.1f} mm3",
            "expected_volume": f"{min_vol:.0f} - {max_vol:.0f} mm3",
            "notes": msg if not success else "OK"
        })
        if use_live_sw:
            try:
                engine.close_document(save=False)
            except Exception:
                pass

    # 2. Failure Injection Cases
    print("\n--- 2. FAILURE INJECTION & PROTECTION TESTS ---")
    sim = CADSimulator()
    for fc in FAILURE_INJECTION_CASES:
        fid = fc["id"]
        fname = fc["name"]
        fplan = fc["plan"]
        should_fail = fc["should_fail_at"]

        rejected = False
        reason = ""

        if should_fail == "schema":
            try:
                validate_cad_plan(fplan)
            except Exception as ex:
                rejected = True
                reason = f"Pydantic caught: {str(ex)[:60]}..."
        elif should_fail == "simulator":
            sim_res = sim.simulate(fplan)
            if not sim_res.valid:
                rejected = True
                reason = f"Simulator caught: {sim_res.errors[0][:60]}..."

        status_icon = "✅ PASS (Engellendi)" if rejected else "❌ FAIL (Fark Edilmedi!)"
        if not rejected:
            all_passed = False

        print(f"[{status_icon}] {fid}: {fname}")
        print(f"       Savunma: {reason}")

        results.append({
            "id": fid,
            "name": fname,
            "status": "PASS" if rejected else "FAIL",
            "duration_ms": 1.0,
            "bodies": "N/A",
            "volume": "N/A",
            "expected_volume": "N/A",
            "notes": reason
        })

    # Generate Markdown Report
    os.makedirs(os.path.join(os.path.dirname(__file__), "results"), exist_ok=True)
    report_path = os.path.join(os.path.dirname(__file__), "results", "benchmark_report.md")

    md = [
        "# SolidAI CAD Reliability & Benchmark Report\n",
        f"**Çalıştırma Modu:** {mode}  ",
        f"**Tarih:** {time.strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Genel Durum:** {'✅ TÜM TESTLER BAŞARILI' if all_passed else '❌ BAZI TESTLER BAŞARISIZ'}\n",
        "## Test Sonuçları Tablosu\n",
        "| Test ID | Test Adı | Durum | Süre (ms) | Gövde Sayısı | Hacim | Beklenen Hacim | Notlar |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]
    for r in results:
        md.append(f"| {r['id']} | {r['name']} | {r['status']} | {r['duration_ms']} | {r['bodies']} | {r['volume']} | {r['expected_volume']} | {r['notes']} |")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print("\n" + "=" * 70)
    print(f" Rapor Kaydedildi: {report_path}")
    print(f" Genel Benchmark Sonucu: {'BAŞARILI (ALL PASS)' if all_passed else 'BAŞARISIZ (FAILURES DETECTED)'}")
    print("=" * 70)
    return all_passed


if __name__ == "__main__":
    use_live = "--live" in sys.argv
    success = run_all_benchmarks(use_live_sw=use_live)
    sys.exit(0 if success else 1)
