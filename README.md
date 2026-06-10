# 💇 AI 换发型

上传你的照片 + 喜欢的发型 → AI 自动生成换发型效果

## 技术方案

- **前端**: Streamlit (Python)
- **AI引擎**: Nano Banana Pro (Gemini 3 Pro Image)
- **API提供商**: laozhang.ai
- **API成本**: $0.09/次（¥0.65）

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env 填入你的 laozhang.ai API Key

# 3. 启动
streamlit run app.py
```

## 定价方案

| 方案 | 次数 | 价格 | 说明 |
|------|------|------|------|
| 🎁 免费试用 | 1次 | ¥0 | 新用户体验 |
| ⭐ 标准包 | 10次 | ¥9.9 | 推荐 |
| 🚀 30天无限包 | 无限 | ¥19.9 | 重度用户 |
| 💡 发型咨询 | 1次 | ¥29.9 | AI脸型分析+推荐 |

## 推广策略

小红书发帖 → 免费试用引流 → 私域成交 → 跑通50单后做网站自动化
