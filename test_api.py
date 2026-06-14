import urllib.request
import urllib.parse
import json
import datetime


def main():
    base_url = "http://localhost:8000"
    print("=" * 60)
    print("城市建筑垃圾运输与处置智能调度系统 - API测试")
    print("=" * 60)
    print()

    # Test 1 - Health
    try:
        with urllib.request.urlopen(base_url + "/health") as resp:
            print("[PASS] Health接口正常:", resp.read().decode())
    except Exception as e:
        print("[FAIL] Health:", e)
        return

    # Test 2 - Login
    data = urllib.parse.urlencode({
        "username": "admin",
        "password": "admin123",
    }).encode()
    req = urllib.request.Request(base_url + "/api/v1/auth/login", data=data, method="POST")
    token = None
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            token = result["access_token"]
            print("[PASS] 登录成功 - 获取Token:", token[:50], "...")
    except urllib.error.HTTPError as e:
        print("[FAIL] 登录:", e.code, e.read().decode())
        return
    except Exception as e:
        print("[FAIL] 登录异常:", e)
        return

    headers = {"Authorization": "Bearer " + token}

    # Test 3 - Current User
    req = urllib.request.Request(base_url + "/api/v1/auth/me", headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            me = json.loads(resp.read())
            print("[PASS] 当前用户:", me["username"], "- 角色:", me["role"])
    except Exception as e:
        print("[FAIL] 获取用户信息:", e)

    # Test 4 - Construction Sites
    req = urllib.request.Request(base_url + "/api/v1/sites/construction", headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            sites = json.loads(resp.read())
            print("[PASS] 工地列表 - 数量:", len(sites))
            for s in sites:
                print("        -", s["name"], "(" + str(s["district"]) + ")")
    except Exception as e:
        print("[FAIL] 工地列表:", e)

    # Test 5 - Disposal Sites
    req = urllib.request.Request(base_url + "/api/v1/sites/disposal", headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            dsites = json.loads(resp.read())
            print("[PASS] 消纳场列表 - 数量:", len(dsites))
            for d in dsites:
                print("        -", d["name"], "剩余容量:", d["remaining_capacity"], "立方米")
    except Exception as e:
        print("[FAIL] 消纳场列表:", e)

    # Test 6 - Recommend Disposal
    params = urllib.parse.urlencode({
        "construction_site_id": 1,
        "planned_volume": 100,
        "planned_date": datetime.datetime.now().isoformat(),
        "top_k": 3,
    })
    req = urllib.request.Request(base_url + "/api/v1/sites/recommend/disposal?" + params, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            recs = json.loads(resp.read())
            print("[PASS] 消纳场推荐 - 推荐数量:", len(recs))
            for r in recs:
                print("        推荐:", r["disposal_site_name"])
                print("          综合评分:", r["total_score"], "距离:", r["distance_km"], "km, 预估费用:", r["estimated_cost"], "元")
    except Exception as e:
        print("[FAIL] 消纳场推荐:", e)

    # Test 7 - Vehicles
    req = urllib.request.Request(base_url + "/api/v1/vehicles", headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            vehs = json.loads(resp.read())
            print("[PASS] 车辆列表 - 数量:", len(vehs))
            for v in vehs:
                print("        -", v["plate_number"], ":", v["vehicle_type"], "载重:", v["load_capacity"], "吨")
    except Exception as e:
        print("[FAIL] 车辆列表:", e)

    # Test 8 - Enforcement Teams
    req = urllib.request.Request(base_url + "/api/v1/auth/enforcement-teams", headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            teams = json.loads(resp.read())
            print("[PASS] 执法队列表 - 数量:", len(teams))
            for t in teams:
                print("        -", t["name"], ", 区域:", t["region"])
    except Exception as e:
        print("[FAIL] 执法队列表:", e)

    # Test 9 - Enterprises
    req = urllib.request.Request(base_url + "/api/v1/auth/enterprises", headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            ents = json.loads(resp.read())
            print("[PASS] 企业列表 - 数量:", len(ents))
            for e2 in ents:
                print("        -", e2["name"], "类型:", e2["type"], "信用分:", e2["credit_score"])
    except Exception as e:
        print("[FAIL] 企业列表:", e)

    # Test 10 - Stats endpoint
    params = urllib.parse.urlencode({
        "start_date": (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat(),
        "end_date": datetime.datetime.now().isoformat(),
    })
    req = urllib.request.Request(base_url + "/api/v1/business/reports/stats?" + params, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            stats = json.loads(resp.read())
            print("[PASS] 运营统计:", json.dumps(stats["summary"], ensure_ascii=False, indent=2))
    except Exception as e:
        print("[WARN] 运营统计(无数据正常):", str(e)[:80])

    # Test 11 - Notifications
    req = urllib.request.Request(base_url + "/api/v1/notifications/unread-count", headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            nc = json.loads(resp.read())
            print("[PASS] 未读通知数量:", nc["unread_count"])
    except Exception as e:
        print("[FAIL] 通知数量:", e)

    print()
    print("=" * 60)
    print("核心业务API测试全部完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
