import json
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

BENCHMARK_FILE = Path(__file__).parent.parent.parent / "Data" / "evaluation" / "copilot_benchmark.json"
BASE_URL = "http://localhost:8000/api/v1/copilot"

def run_benchmark():
    if not BENCHMARK_FILE.exists():
        print(f"Error: {BENCHMARK_FILE.resolve()} not found.")
        return

    with open(BENCHMARK_FILE, "r") as f:
        cases = json.load(f)

    # Create a conversation
    req = urllib.request.Request(f"{BASE_URL}/conversations", data=b"{}", headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as response:
        convo = json.loads(response.read().decode())
        convo_id = convo["conversation_id"]

    results = []
    print(f"Running {len(cases)} benchmark cases against conversation {convo_id}...")

    for i, case in enumerate(cases, 1):
        question = case["question"]
        expected = case["allowed_answer_state"]
        
        payload = json.dumps({"message": question, "filters": {"include_ai_proposed": True, "include_synthetic_demo": True}}).encode("utf-8")
        req = urllib.request.Request(f"{BASE_URL}/conversations/{convo_id}/messages", data=payload, headers={'Content-Type': 'application/json'})
        
        t0 = time.time()
        try:
            with urllib.request.urlopen(req) as response:
                ans = json.loads(response.read().decode())
                latency_ms = int((time.time() - t0) * 1000)
                status = ans["answer_status"]
                
                passed = status == expected
                if expected == "insufficient_evidence" and status == "safety_boundary":
                    # For some missing evidence, safety boundary is also accepted
                    passed = True
                
                results.append({
                    "case": i,
                    "group": case.get("group", ""),
                    "question": question,
                    "expected": expected,
                    "actual": status,
                    "latency": latency_ms,
                    "passed": passed,
                })
                print(f"[{'PASS' if passed else 'FAIL'}] Q{i}: {question[:40]}... (latency: {latency_ms}ms) -> {status}")
        except Exception as e:
            print(f"[ERROR] Q{i}: {str(e)}")

    # Print markdown summary
    print("\n## Benchmark Results\n")
    print("| Case | Group | Question | Expected | Actual | Latency | Result |")
    print("|---|---|---|---|---|---|---|")
    for r in results:
        pass_str = "PASS" if r['passed'] else "FAIL"
        lat = r['latency']
        lat_str = f"{lat}ms" if lat < 2500 else f"**{lat}ms**"
        print(f"| {r['case']} | {r['group']} | {r['question']} | {r['expected']} | {r['actual']} | {lat_str} | {pass_str} |")

if __name__ == "__main__":
    run_benchmark()
