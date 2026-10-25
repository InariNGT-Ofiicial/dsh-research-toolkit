# Zotero 0.2.2 原生 JSON 兼容修复

上游 MIT 源码：Hongcheng-LI/dsh-zotero，commit e4042d5139aa81d810b95928d63632f80a32a7ac。此本地派生包版本为 0.2.2-research.1。仅在原生注册边界移除对象中值为 undefined 的可选字段；拒绝 NaN、Infinity、undefined 数组元素和其他非 JSON 值，不改变工具 schema、请求或权限。原 MIT LICENSE 随派生包保留。

```diff
--- upstream/lib/index.js
+++ compat/lib/index.js
@@ -128,6 +128,10 @@
     return oneText(`无法解析附件 ${value.attachmentKey} 的本地路径（storage 目录未找到或文件不在预期位置）。可在 cordis.patch.yml 配置 storageDir / dataDir，或改用 zotero_download。`);
 }
 export function apply(ctx, config = {}) {
+    const register = (definition) => {
+        const execute = definition.execute;
+        return ctx.tools.register({ ...definition, async execute(...args) { return losslessResult(await execute(...args)); } });
+    };
     const resolved = resolveConfig(config);
     const client = new ZoteroClient(resolved);
     const storageDir = resolveStorageDir({ dataDir: resolved.dataDir, storageDir: resolved.storageDir });
@@ -138,7 +142,7 @@
     if (storageDir === null) {
         ctx.logger?.info?.('[dsh-zotero] 未找到 Zotero storage 目录，zotero_fulltext 将退化为下载附件；可在 cordis.patch.yml 配置 storageDir/dataDir');
     }
-    ctx.tools.register({
+    register({
         name: 'zotero_collections',
         description: 'List the collections (folders) of the Zotero library, with their keys and item counts. Use a returned collectionKey as the collection argument of zotero_search to scope a search. Requires Zotero 7+ (tested on 9.x) running locally with "Allow other applications on this computer" enabled.',
         parameters: {
@@ -153,7 +157,7 @@
             return { collections: await client.collections() };
         },
     });
-    ctx.tools.register({
+    register({
         name: 'zotero_search',
         description: 'Search the local Zotero library by keyword (title/creator/year, Zotero quick-search), with filters for item type, collection, tag and publication year range, plus sorting and pagination. Control payload size with mode. Returns compact rows with item keys; use zotero_item with a key for full metadata and attachments.',
         parameters: {
@@ -202,7 +206,7 @@
             return { count: items.length, totalResults, items: trimItems(items, parseMode(args.mode)) };
         },
     });
-    ctx.tools.register({
+    register({
         name: 'zotero_recent',
         description: 'List the most recently ADDED items of the Zotero library (newest first, attachments and notes excluded). Use it for "what did I just import" questions; use zotero_item with a key for details.',
         parameters: {
@@ -236,7 +240,7 @@
             return { count: trimmed.length, items: trimmed };
         },
     });
-    ctx.tools.register({
+    register({
         name: 'zotero_item',
         description: 'Read one Zotero item in full by its key (from zotero_search): authors, publication venue, DOI, abstract and tags, plus its child attachments (PDF keys) and note count.',
         parameters: {
@@ -256,7 +260,7 @@
             return await client.item(key);
         },
     });
-    ctx.tools.register({
+    register({
         name: 'zotero_fulltext',
         description: 'Read the full text of a Zotero item (its PDF or other main attachment) as plain text — from Zotero\'s own fulltext cache (.zotero-ft-cache) when available, otherwise parsed on the fly from the local PDF (pdfjs-dist) and cached. Only for remote-link-only attachments does it download a copy to the workspace and return its path. Prefer this over zotero_download when you only need the text.',
         parameters: {
@@ -362,7 +366,7 @@
             return { itemKey, attachmentKey: target.key, filename, contentType, mode: 'file', size: bytes.byteLength, path };
         },
     });
-    ctx.tools.register({
+    register({
         name: 'zotero_download',
         description: 'Download one attachment (typically a PDF) of a Zotero item to the local filesystem — by default into the session workspace so the model can read it. Use the attachmentKey values listed by zotero_item. If you only need the text, prefer zotero_fulltext. Size is capped by maxAttachmentBytes.',
         parameters: {
@@ -397,7 +401,7 @@
             return { key: attachmentKey, filename, contentType, size: bytes.byteLength, path };
         },
     });
-    ctx.tools.register({
+    register({
         name: 'zotero_attachment_path',
         description: 'Resolve the on-disk path of a stored attachment (zero-copy): returns the absolute path inside Zotero storage so the model can read the original file directly. Works for stored attachments; linked attachments report their recorded path.',
         parameters: {
@@ -446,7 +450,7 @@
             return { itemKey, attachmentKey, path: target.path ?? '', exists: false };
         },
     });
-    ctx.tools.register({
+    register({
         name: 'zotero_notes',
         description: 'List or search the notes of the Zotero library: with itemKey, the child notes of that item; otherwise a library-wide keyword search over note text (newest first). Returns noteKeys for zotero_note (append/update/delete).',
         parameters: {
@@ -475,7 +479,7 @@
             return { count: notes.length, notes };
         },
     });
-    ctx.tools.register({
+    register({
         name: 'zotero_note',
         description: 'Write notes to Zotero: create a child note under an item, or append to / update / delete an existing note (noteKeys from zotero_notes). Only write notes the user asked for; never invent content.',
         parameters: {
@@ -527,3 +531,16 @@
     // Keep ZoteroError referenced so the error type survives bundling.
     void ZoteroError;
 }
+
+// DSH Research Toolkit compatibility patch: optional object fields must not
+// contain undefined under the native ToolRuntime's lossless JSON contract.
+// Reject unsupported values rather than silently converting NaN/Infinity.
+export function losslessResult(value) {
+    if (value === null || typeof value === 'string' || typeof value === 'boolean') return value;
+    if (typeof value === 'number' && Number.isFinite(value)) return value;
+    if (Array.isArray(value)) return value.map(losslessResult);
+    if (value && Object.getPrototypeOf(value) === Object.prototype) {
+        return Object.fromEntries(Object.entries(value).filter(([,v]) => v !== undefined).map(([k,v]) => [k,losslessResult(v)]));
+    }
+    throw new TypeError('Zotero output contains a non-JSON value');
+}

```
