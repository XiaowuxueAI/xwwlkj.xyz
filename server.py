#!/usr/bin/env python3
"""
AI创富工具箱 · 全栈客服聊天 + 下单系统后端
Flask + SQLite, 运行在本地, 通过localtunnel穿透
启动: python3 server.py
"""
import os, json, time, sqlite3, smtplib
from email.mime.text import MIMEText
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DB = os.path.join(os.path.dirname(__file__), 'data.db')

# ======================== 数据库 ========================
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product TEXT NOT NULL,
            customer_name TEXT DEFAULT '',
            contact TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT DEFAULT '待处理',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_msg_session ON messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_order_status ON orders(status);
    ''')
    conn.commit()
    conn.close()

init_db()

# ======================== AI 自动回复 ========================
FAQ = {
    '价格': '您好！我们的产品分四档：\n💰 ¥1 提示词大礼包 — AI提示词合集\n💰 ¥9.9 文案脚本模板 — 含售后修改\n💰 ¥29.9 全能包 — Python脚本+网站搭建+API教程\n💰 ¥50-3000 定制服务 — 一对一专属开发\n\n详情请在首页查看各档位说明~',
    '多少钱': '您好！我们的产品分四档：\n💰 ¥1 提示词大礼包\n💰 ¥9.9 文案脚本模板（含售后修改）\n💰 ¥29.9 全能包（Python+网站+API）\n💰 ¥50-3000 定制服务\n\n点击首页价格卡片即可购买！',
    '交付': '付款后我们会尽快处理：\n📦 标准产品：付款后5分钟内自动发货\n🔧 定制服务：根据需求复杂度1-3个工作日\n\n如有急单请加微信，5分钟响应！',
    '发货': '付款后我们会尽快处理：\n📦 标准产品：付款后5分钟内自动发货\n🔧 定制服务：1-3个工作日\n\n急单加微信，5分钟响应！',
    '多久': '标准产品付款后5分钟内发货，定制服务1-3个工作日。急单加微信5分钟响应！',
    '怎么买': '在首页选择您需要的产品档位，点击价格卡片即可看到付款码和购买说明。\n\n付款后截图发送给客服微信即可。',
    '付款': '我们支持微信和支付宝付款。在首页点击价格卡片可看到收款码。\n\n付款后请截图发给客服微信确认。',
    '售后': '我们提供完善的售后服务：\n✅ ¥9.9及以上档位含售后修改\n✅ 定制服务含无限次修改直到满意\n✅ 急单/定制请加微信沟通',
    '微信': '请添加客服微信：扫描页面底部二维码\n急单/定制加微信，5分钟响应！',
    '定制': '我们提供¥50-3000的定制开发服务：\n🔧 Python脚本开发\n🌐 网站搭建\n📊 数据分析\n🤖 AI应用开发\n\n请联系微信详谈需求！',
    '联系': '📱 客服微信：扫描页面底部二维码\n⏰ 工作时间：每天9:00-22:00\n🔥 急单/定制加微信，5分钟响应！',
    '你好': '您好！👋 欢迎来到AI创富工具箱！\n\n我是AI客服助手，可以帮您解答产品、价格、购买等问题。\n如需人工服务，请说"转人工"或直接加微信~',
}

def ai_reply(message):
    """简单关键词匹配AI回复"""
    msg = message.lower().strip()
    for keyword, reply in FAQ.items():
        if keyword in msg:
            return reply
    # 没有匹配 → 转人工
    return None

# ======================== 邮件通知 ========================
SMTP_CONFIG = {
    'host': os.environ.get('SMTP_HOST', ''),
    'port': int(os.environ.get('SMTP_PORT', '465')),
    'user': os.environ.get('SMTP_USER', ''),
    'pass': os.environ.get('SMTP_PASS', ''),
    'to': os.environ.get('SMTP_TO', ''),  # 你的邮箱
}

def send_order_email(order):
    """发送订单通知邮件"""
    if not SMTP_CONFIG['host'] or not SMTP_CONFIG['to']:
        # SMTP未配置 → 保存本地通知
        notify_file = os.path.join(os.path.dirname(__file__), 'order_notifications.json')
        try:
            with open(notify_file, 'r') as f:
                notes = json.load(f)
        except:
            notes = []
        notes.append({**order, 'notified': datetime.now().isoformat()})
        with open(notify_file, 'w') as f:
            json.dump(notes, f, ensure_ascii=False, indent=2)
        print(f"[订单通知] 新订单已保存到 {notify_file}")
        return False

    try:
        body = f"""新订单通知

产品：{order['product']}
客户：{order.get('customer_name', '未填')}
联系方式：{order['contact']}
需求描述：{order['description']}
下单时间：{order['created_at']}
状态：待处理

请尽快联系客户！
"""
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = f'新订单 - {order["product"]} - {order.get("customer_name", "新客户")}'
        msg['From'] = SMTP_CONFIG['user']
        msg['To'] = SMTP_CONFIG['to']

        with smtplib.SMTP_SSL(SMTP_CONFIG['host'], SMTP_CONFIG['port']) as smtp:
            smtp.login(SMTP_CONFIG['user'], SMTP_CONFIG['pass'])
            smtp.send_message(msg)
        print(f"[邮件通知] 已发送到 {SMTP_CONFIG['to']}")
        return True
    except Exception as e:
        print(f"[邮件通知失败] {e}")
        return False

# ======================== API 路由 ========================

@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({'status': 'ok', 'time': datetime.now().isoformat()})

# --- 聊天 ---
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json(force=True)
    session_id = data.get('session_id', 'default')
    message = data.get('message', '').strip()

    if not message:
        return jsonify({'error': 'empty message'}), 400

    # 存用户消息
    db = get_db()
    db.execute('INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)',
               [session_id, 'user', message])
    db.commit()

    # AI回复
    reply = ai_reply(message)
    if reply:
        db.execute('INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)',
                   [session_id, 'ai', reply])
        db.commit()
        db.close()
        return jsonify({'reply': reply, 'status': 'ai'})

    # 转人工
    fallback = ('非常抱歉，我暂时无法回答这个问题 😅\n\n'
                '已为您转接人工客服，请稍候～\n'
                '或直接扫描页面底部二维码添加微信，5分钟响应！')
    db.execute('INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)',
               [session_id, 'ai', fallback])
    db.commit()
    db.close()
    return jsonify({'reply': fallback, 'status': 'transfer'})

@app.route('/api/chat/history', methods=['GET'])
def chat_history():
    session_id = request.args.get('session_id', 'default')
    db = get_db()
    rows = db.execute(
        'SELECT role, content, created_at FROM messages WHERE session_id=? ORDER BY id ASC',
        [session_id]
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

# --- 订单 ---
@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.get_json(force=True)
    required = ['product', 'contact', 'description']
    for field in required:
        if not data.get(field, '').strip():
            return jsonify({'error': f'缺少必填字段: {field}'}), 400

    db = get_db()
    db.execute(
        'INSERT INTO orders (product, customer_name, contact, description, status) VALUES (?, ?, ?, ?, ?)',
        [data['product'].strip(),
         data.get('customer_name', '').strip(),
         data['contact'].strip(),
         data['description'].strip(),
         '待处理']
    )
    db.commit()
    order_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
    order = dict(db.execute('SELECT * FROM orders WHERE id=?', [order_id]).fetchone())
    db.close()

    # 尝试邮件通知
    send_order_email(order)

    return jsonify({
        'success': True,
        'order_id': order_id,
        'status': '待处理',
        'message': '订单已提交！我们会尽快联系您。急单请加微信，5分钟响应。'
    })

@app.route('/api/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    db = get_db()
    order = db.execute('SELECT * FROM orders WHERE id=?', [order_id]).fetchone()
    db.close()
    if not order:
        return jsonify({'error': '订单不存在'}), 404
    return jsonify(dict(order))

# ======================== 启动 ========================
if __name__ == '__main__':
    print(f'数据库: {DB}')
    print('启动客服后端... http://127.0.0.1:5000')
    app.run(host='127.0.0.1', port=5000, debug=False)
