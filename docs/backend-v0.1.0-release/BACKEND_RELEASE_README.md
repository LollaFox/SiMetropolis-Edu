# Northern Metropolis backend / 北部都会区后端

**v0.1.0 · First internal release / 首个内部版本 · 2026-10-16**

Working simulation backend with the original frontend bundled unchanged. Python 3.9+; standard library only, no dependency installation required. Regional objects are synthetic development clusters, not individual physical towers or a validated forecast.

可运行的模拟后端，附带未修改的原前端。使用 Python 3.9 及以上版本，无需安装第三方依赖。区域对象代表示意性开发组团，并非真实单栋楼宇；结果用于沙盒演示。

- [Release notes / 版本说明](backend/docs/releases/RELEASE_NOTES.md)
- Frontend handoff / 前端交接：[English](backend/docs/releases/FRONTEND_HANDOFF_EN.md) · [中文](backend/docs/releases/FRONTEND_HANDOFF_ZH.md)
- Historical city data / 历史城市数据：[English](backend/docs/releases/CITY_HISTORY_EN.md) · [中文](backend/docs/releases/CITY_HISTORY_ZH.md)
- [Detailed backend guide / 后端详细说明](backend/README.md)

## Classroom downloads / 課堂下載

For the Long Valley classroom, follow the [English startup guide](../../README.md). 塱原課堂的下載和啟動步驟見[繁體中文說明](../../README_ZH.md)。

## Government examples and original handoff / 政府示例及原始交接

Edit a copy of [the regional government script](backend/examples/northern-metropolis-scenario.json); see the frontend handoff for the exact loader and execution files. Historical city data has its own separate guides linked above.

请复制上述区域政府脚本再编辑；加载与执行代码位置见前端交接文档。历史城市数据读取方法见上方独立指南。

The root `00_*`, `01_*`, `02_*`, `发给后端同学.txt` and `MANIFEST.json` belong to the original frontend handoff. They are historical references; use this release's handoff for the implemented backend contract. `RELEASE_MANIFEST.json` beside the release ZIP identifies the new package. Internal collaborator distribution only; existing licensing and Three.js notices are preserved, with no relicensing or public publication.

根目录原有交接说明及 `MANIFEST.json` 是旧前端交接资料；当前后端接口以本版本交接文档为准。ZIP 旁的 `RELEASE_MANIFEST.json` 描述本次发布包。本版本用于内部协作，保留原有许可和 Three.js 声明，不变更许可、不公开发布。
