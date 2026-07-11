import sys, os, json
sys.path.insert(0, '/home/ubuntu/napcat_egg_bot')
os.chdir('/home/ubuntu/napcat_egg_bot')
from egg_calculator import EggCalculator

calculator = EggCalculator(
    "PET_EGG_CONF.json", "全图鉴.json", "蛋组.json",
    "PET_EGG_CONF1.json", "PET_EGG_CONF_RANDOM.json"
)

from flask import Flask, request, jsonify
import time
from collections import defaultdict

# 每日限流（每 IP 50000 次）
_daily_limit = 50000
_daily_count = defaultdict(int)
_daily_date = time.strftime("%Y-%m-%d")

def check_daily_limit(ip):
    global _daily_date, _daily_count
    today = time.strftime("%Y-%m-%d")
    if today != _daily_date:
        _daily_count.clear()
        _daily_date = today
    _daily_count[ip] += 1
    return _daily_count[ip] <= _daily_limit

app = Flask(__name__)
API_TOKEN = os.environ.get("API_TOKEN", "")

@app.route("/api/compute", methods=["POST"])
def api_compute():
    ip = request.remote_addr
    if not check_daily_limit(ip):
        return jsonify({"result": "每日请求次数已达上限（50000次）"}), 429
    data = request.get_json()
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if API_TOKEN and token != API_TOKEN:
        return jsonify({"result": "未授权"}), 401
    attr = data.get("attribute", "")
    val = data.get("data", "").strip()
    if attr == "精灵查询":
        r = calculator.query_encyclopedia(val)
        return jsonify({"result": r if r else "未找到"})
    elif attr == "蛋组查询":
        # 多蛋组交集
        import re as _re
        sep = _re.split(r"[/xX×]+", val)
        if len(sep) >= 2:
            group_keys = [s.strip() for s in sep if s.strip() in calculator.egg_groups]
            if len(group_keys) >= 2:
                sets = []
                for g in group_keys:
                    spirits = calculator.egg_groups.get(g, [])
                    names = {sp.get("name", "") for sp in spirits}
                    if names:
                        sets.append(names)
                if sets:
                    common = set.intersection(*sets)
                    if common:
                        ordered = [s for s in calculator.encyclopedia if s.get("name", "") in common]
                        lines = [f"—— {' x '.join(group_keys)} 共有精灵 ——"]
                        for ss in ordered:
                            eg = ss.get("egg_groups", [])
                            eg_str = f"（{'、'.join(eg)}）" if eg else ""
                            lines.append(f"  {ss['name']}{eg_str}")
                        return jsonify({"result": "\n".join(lines)})
                    return jsonify({"result": f"—— {' x '.join(group_keys)} 无共有精灵 ——"})
        r = calculator.query_by_egg_group(val)
        return jsonify({"result": r if r and "未找到" not in r else "未找到蛋组"})
    elif attr == "孵蛋预测":
        parts = val.split()
        if len(parts) >= 2:
            h = calculator.parse_height(parts[0])
            w = calculator.parse_weight(parts[1])
            return jsonify({"result": calculator.predict_by_size_weight(h, w)})
        return jsonify({"result": "参数错误"})
    return jsonify({"result": "未知属性"})

@app.route("/")
def index():
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8">
<title>蛋数据查询</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Microsoft YaHei",sans-serif;background:#0f1117;color:#e1e4e8;padding:20px}
.container{max-width:800px;margin:0 auto}
h1{font-size:22px;margin-bottom:16px;background:linear-gradient(135deg,#58a6ff,#bc8cff);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.card{background:#1c1e26;border:1px solid #30363d;border-radius:12px;padding:20px;margin-bottom:16px}
label{color:#8b949e;font-size:14px;display:block;margin-bottom:6px}
select,input,textarea{width:100%;padding:10px 14px;background:#0d1117;border:1px solid #30363d;border-radius:8px;color:#e1e4e8;font-size:15px;outline:none;margin-bottom:10px}
select:focus,input:focus,textarea:focus{border-color:#58a6ff}
textarea{height:200px;resize:vertical;font-family:monospace}
.btn{padding:10px 24px;background:#238636;color:#fff;border:none;border-radius:8px;font-size:15px;cursor:pointer}
.btn:hover{background:#2ea043}
</style></head>
<body><div class="container">
<h1>❎ 蛋数据查询</h1>
<div class="card">
<label>属性</label>
<select id="attr">
<option value="精灵查询">精灵查询</option>
<option value="蛋组查询">蛋组查询</option>
<option value="孵蛋预测">孵蛋预测</option>
</select>
<label>数据</label>
<input id="data" value="火花" placeholder="输入内容">
<button class="btn" onclick="query()">查询</button>
</div>
<div class="card">
<label>结果</label>
<textarea id="output" readonly placeholder="结果..."></textarea>
</div>
</div>
<script>
function query(){
var a=document.getElementById("attr").value;
var d=document.getElementById("data").value;
var o=document.getElementById("output");
o.value="查询中...";
fetch("/api/compute",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({attribute:a,data:d})})
.then(r=>r.json()).then(j=>{o.value=j.result}).catch(e=>{o.value="失败: "+e});
}
</script></body></html>"""

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "daily_requests": dict(_daily_count)})



if __name__ == "__main__":

    app.run(host="127.0.0.1", port=9426, debug=False)
