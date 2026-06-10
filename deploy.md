# 🚀 部署指南

## 方式一：Cloudflare Tunnel（推荐，免费）

1. 下载 cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
2. 运行: `cloudflared tunnel --url http://localhost:8501`
3. 会得到一个 `https://xxx.trycloudflare.com` 的公网地址
4. 把这个地址发给别人就能用

## 方式二：局域网分享

同一 WiFi 下，别人访问 `http://你的局域网IP:8501`
- 查看 IP: 启动日志里的 `Network URL`

## 方式三：部署到服务器

```bash
# 在服务器上
git clone <repo> 
pip install -r requirements.txt
# 配置 .env 文件
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

## 方式四：Streamlit Cloud（免费）

1. 把代码推送到 GitHub 公开仓库
2. 在 share.streamlit.io 部署
3. 自动获得公网 URL

## 后台管理

访问应用后，侧边栏底部"后台管理"：
- 密码: `admin888`
- 可查看用户、设备、充值、设置付费会员
