# AK 配置指南

## AK 格式规范

AK（Access Key）是访问 1688 平台的身份凭证。

- 长度：≥ 32 位
- 允许字符：`A-Z a-z 0-9 _ - =`
- 结构：前 32 位是 Secret，其余是 Key ID

## 获取 AK（引导用户）

当用户没有 AK 时，Agent 输出以下引导：

> 打开 [**1688 AI版 APP**](https://air.1688.com/kapp/1688-ai-app/pages/home?from=1688-shopkeeper)（没装的话点链接下载），首页点击「一键部署开店Claw，全自动化赚钱🦞」，进入页面复制 AK，然后告诉我：'我的AK是 xxx'

## Agent 配置流程（核心）

用户告知 AK 后，Agent 按以下步骤执行：

```
1. 从用户消息中提取 AK 字符串
2. 执行 cli.py configure <AK>
3. 检查输出：success=true → 继续；success=false → 展示错误
4.【必须】当前会话后续所有命令前加 ALI_1688_AK=<AK> 前缀
   例如：ALI_1688_AK=xxxyyy python3 cli.py search --query "连衣裙"
   原因：configure 写入配置文件后需重启 Gateway 才全局生效，
   但加环境变量前缀可让当前会话立即可用
5. 继续用户的原始请求（如搜索、铺货等）
```

## CLI 调用

```bash
# 写入 AK
python3 {baseDir}/cli.py configure YOUR_AK_HERE

# 查看当前状态（不传参数）
python3 {baseDir}/cli.py configure
```

## CLI 输出

### 配置成功

```json
{
  "success": true,
  "markdown": "✅ AK 已保存: `abcd****wxyz`\n\n⚠️ 重启 Gateway 使配置全局生效: `openclaw gateway restart`\n\n当前会话立即使用: `ALI_1688_AK=abcd...wxyz python3 cli.py search --query \"XXX\"`",
  "data": {"configured": true}
}
```

### 配置失败

```json
{
  "success": false,
  "markdown": "❌ AK 长度不足（当前 20，需要至少 32 位）",
  "data": {"configured": false}
}
```

可能的失败原因：
- AK 为空
- AK 不合法
- Gateway 不可用且 fallback 写入被拒绝（配置文件为 JSON5 格式）

### 查看状态（无参数）

```json
{
  "success": true,
  "markdown": "✅ AK 已配置: `abcd****wxyz`（来源: 环境变量（已生效））",
  "data": {"configured": true}
}
```

## 检查整体配置状态

```bash
python3 {baseDir}/cli.py check
```

输出 AK 状态、绑定店铺数量、数据目录可写状态。用于首次使用时的全面检查。

## 异常处理

| 场景 | Agent 应对 |
|------|-----------|
| 用户给的 AK 格式异常 | 提示"AK 看起来不完整，请确认是否完整复制" |
| configure 输出 success=false | 原样输出 markdown 错误信息 |
| 配置成功但后续命令仍报 AK 未配置 | 检查是否忘记加 `ALI_1688_AK=xxx` 前缀 |
| 用户问"我的 AK 在哪" | 输出获取 AK 引导话术 |

## 安全提示

- AK 仅用于本地 API 调用，不上传服务器
- 建议定期轮换 AK（在 1688 AI版 APP 重新生成）
- 不要将 AK 提交到代码仓库
