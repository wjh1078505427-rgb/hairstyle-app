# 🚀 部署指南

## 方式一：Serveo 永久隧道（推荐，免费，重启不变！）

地址永久固定：`https://ai-hairstyle.serveo.net`

首次注册（仅一次，1分钟）：
1. 打开 https://console.serveo.net/ssh/keys?add=SHA256:qhSN/VfEl1bUDkdGpM8B4SmScUVaeS8kh/OYJj+a2mg
2. 用 Google 或 GitHub 登录
3. 之后每次启动只需运行:
   ```bash
   ssh -R ai-hairstyle:80:localhost:8501 serveo.net
   ```

零下载，用系统自带的 SSH 即可。

## 方式二：Cloudflare Tunnel（备选）

1. 下载 cloudflared
2. 运行: `cloudflared tunnel --url http://localhost:8501`
3. ⚠️ 免费版地址重启后会变

## 方式三：局域网分享

同一 WiFi 下，别人访问 `http://你的局域网IP:8501`
- 查看 IP: 启动日志里的 `Network URL`

## 方式四：部署到服务器

```bash
# 在服务器上
git clone <repo> 
pip install -r requirements.txt
# 配置 .env 文件
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

## 方式五：Streamlit Cloud（免费）

1. 把代码推送到 GitHub 公开仓库
2. 在 share.streamlit.io 部署
3. 自动获得公网 URL

## 后台管理

访问应用后，侧边栏底部"后台管理"：
- 密码: `admin888`
- 可查看用户、设备、充值、设置付费会员
