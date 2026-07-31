# 阶段 16：多模态情报与实时协同

## 已实现范围

- 图片：格式与魔数校验、OCR、截图理解、图表结构提取、区域级 `bbox` 证据。
- 音频：真实模型转写、分段时间戳、模型返回的说话人标签和观点原文。模型不返回说话人时明确标记 `speaker_unknown`。
- 视频：FFprobe 元数据、FFmpeg 限量抽帧、音轨提取、帧级视觉证据、字幕时间段和关键帧定位。
- 媒体治理：SHA-256 内容哈希、图片感知哈希、租户内幂等、S3 兼容存储、版权/授权状态、PII 复核和彻底删除。
- 实时情报：直播流、单调递增更新序列、Redis 发布、结束状态和更新补拉。
- 协作：报告与工作流文档、乐观锁、非重叠自动合并、路径冲突、评论、组织内提及、一次性 WebSocket ticket、在线状态和审计。
- 模型治理：租户 ModelRoute、月度成本上限、处理成本、成功率和证据置信度统计。
- 移动采集：响应式采集工作区、相机/媒体选择、授权、版权、来源和现场元数据。

系统不生成模拟 OCR、字幕、说话人、图表结论或视频摘要。模型凭据、批准路由或 FFmpeg 缺失时，处理任务以可诊断失败结束。

## 证据与引用

每条 `MediaEvidence` 保存原始资产、文本、内容哈希以及适用的 `bbox`、`start_ms/end_ms`、`frame_number`、`speaker` 和帧存储键。引用创建前验证租户和目标资源权限。删除资产后，原件、抽帧、证据和媒体引用均不可继续访问。

## 协作一致性

持久化变更只能通过带 `base_version` 的 REST 接口提交。WebSocket 不接受文档写入，只承载 presence 和已提交事件。服务端检查受控 `set/remove` 操作、路径深度、原型污染、客户端序列幂等和路径交集。报告变更同步创建不可变 `ReportVersion`。

## 生产配置

API 不内嵌生产 Worker。部署独立 `media-worker`，挂载相同 S3、数据库、Redis 和模型密钥；镜像必须包含 FFmpeg/FFprobe。设置：

```text
MEDIA_WORKER_ENABLED=true
MEDIA_MAX_FILE_MB=250
MEDIA_VISION_MODEL=<approved model id>
MEDIA_TRANSCRIPTION_MODEL=<approved model id>
MEDIA_FRAME_INTERVAL_SECONDS=10
MEDIA_MAX_VIDEO_FRAMES=24
```

反向代理上传上限必须略高于 `MEDIA_MAX_FILE_MB`。告警覆盖 Worker 无副本及 15 分钟处理失败突增。成本异常、PII 命中、未授权音视频与版权状态未知应进入人工复核。

## 运维验证

1. 上传真实 PNG，确认 OCR 只包含可见内容且 `bbox` 可定位。
2. 上传已授权 WAV，确认分段时间戳；模型不支持分离时不得出现伪说话人。
3. 上传短 MP4，确认抽帧数量不超过配置、时间跳转正确且临时文件清理。
4. 使用相同文件重复上传，确认返回同一租户资产；跨租户不得复用记录。
5. 并发编辑同一路径，确认产生冲突；编辑不同路径，确认自动合并。
6. 消费 WebSocket ticket 后再次连接，确认拒绝；过期 ticket 同样拒绝。
7. 删除资产后确认原件、帧、证据接口和引用均返回不可用。

真实供应商模型、S3、Redis 和生产域名需要由部署方注入凭据，本仓库不包含或声明这些外部资源已开通。
