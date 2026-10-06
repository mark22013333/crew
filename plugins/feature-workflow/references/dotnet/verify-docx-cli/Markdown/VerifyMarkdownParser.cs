using System.Text;
using System.Text.RegularExpressions;
using Markdig;
using Markdig.Extensions.Tables;
using Markdig.Syntax;
using Markdig.Syntax.Inlines;

namespace FeatureWorkflow.VerifyDocxCli.Markdown;

public static class VerifyMarkdownParser
{
    // 表格擴充必須開：fixture 的環境/摘要/待處理/版本紀錄全是 pipe table
    private static readonly MarkdownPipeline Pipeline =
        new MarkdownPipelineBuilder().UseAdvancedExtensions().Build();

    public static VerifyReport Parse(string verifyMdContent, CoverInfo cover)
    {
        var doc = Markdig.Markdown.Parse(verifyMdContent, Pipeline);
        var env = ExtractEnvInfo(doc);
        var summary = ExtractSummary(doc);
        var details = ExtractDetails(doc);
        var pending = ExtractPending(doc);
        var versions = ExtractAppendixVersions(doc);
        return new VerifyReport(cover, env, summary, details, pending, versions);
    }

    // ── 測試環境 ────────────────────────────────────────────────
    private static EnvInfo ExtractEnvInfo(MarkdownDocument doc)
    {
        var map = TableToKeyValue(FindFirstTable(SectionBlocks(doc, "測試環境")));
        return new EnvInfo(
            Url: map.GetValueOrDefault("測試 URL", ""),
            Browser: map.GetValueOrDefault("瀏覽器", ""),
            Role: map.GetValueOrDefault("測試帳號角色", ""),
            DataDescription: map.GetValueOrDefault("測試資料說明", ""),
            Prerequisites: map.GetValueOrDefault("前置條件", ""));
    }

    // ── 驗收摘要 ────────────────────────────────────────────────
    private static SummaryStats ExtractSummary(MarkdownDocument doc)
    {
        var blocks = SectionBlocks(doc, "驗收摘要");
        var map = TableToKeyValue(FindFirstTable(blocks));

        int Read(string key) => int.TryParse(map.GetValueOrDefault(key, "").Trim(), out var n) ? n : 0;
        int pass = Read("通過"), fail = Read("未通過"), warn = Read("警告"),
            blocked = Read("前置阻擋"), skip = Read("略過"), manual = Read("待人工確認");

        // 結論：表格後第一個含「結論」的段落
        var conclusion = FindConclusion(blocks) ?? GenerateConclusion(pass, fail, warn, blocked, skip, manual);
        return new SummaryStats(pass, fail, warn, blocked, skip, manual, conclusion);
    }

    private static string? FindConclusion(List<Block> blocks)
    {
        foreach (var b in blocks)
        {
            if (b is ParagraphBlock p)
            {
                var text = GetInlineText(p.Inline).Trim();
                if (text.StartsWith("結論")) return text.TrimStart('結', '論', '：', ':').Trim();
            }
        }
        return null;
    }

    private static string GenerateConclusion(int pass, int fail, int warn, int blocked, int skip, int manual)
    {
        var total = pass + fail + warn + blocked + skip + manual;
        if (fail > 0) return $"共 {total} 項驗收條件，{fail} 項未通過，需修正後重新驗證。";
        if (blocked > 0) return $"共 {total} 項驗收條件，{blocked} 項因前置條件阻擋，排除阻擋後需重新驗證。";
        if (warn > 0 || manual > 0) return $"共 {total} 項驗收條件，{pass} 項通過、{warn} 項警告、{manual} 項待人工確認。";
        return $"共 {total} 項驗收條件全數通過。";
    }

    // ── 驗收明細 ────────────────────────────────────────────────
    private static List<DetailItem> ExtractDetails(MarkdownDocument doc)
    {
        var details = new List<DetailItem>();
        var blocks = SectionBlocks(doc, "驗收明細");

        // 以 H3 切分子段
        var groups = SplitByHeading(blocks, level: 3);
        foreach (var (heading, body) in groups)
        {
            var (number, title) = ParseDetailHeading(heading);
            details.Add(BuildDetailItem(number, title, body));
        }
        return details;
    }

    private static (int Number, string Title) ParseDetailHeading(string heading)
    {
        // 「驗收項目 1：可依日期範圍查詢推播統計」
        var m = Regex.Match(heading, @"驗收項目\s*(\d+)\s*[:：]\s*(.+)");
        if (m.Success) return (int.Parse(m.Groups[1].Value), m.Groups[2].Value.Trim());
        return (0, heading.Trim());
    }

    private static DetailItem BuildDetailItem(int number, string title, List<Block> body)
    {
        var status = DetailStatus.Manual;
        var steps = new List<string>();
        string expected = "", actual = "";
        var apiCalls = new List<ApiCall>();
        var screenshots = new List<string>();

        string? pendingLabel = null;
        bool expectSteps = false;
        string? pendingRequestCode = null;

        foreach (var b in body)
        {
            switch (b)
            {
                case ParagraphBlock p:
                {
                    var text = GetInlineText(p.Inline).Trim();
                    if (text.StartsWith("結果")) status = ParseStatusIcon(text);
                    else if (text.StartsWith("操作步驟")) expectSteps = true;
                    else if (text.StartsWith("預期結果")) expected = StripLabel(text, "預期結果");
                    else if (text.StartsWith("實際結果")) actual = StripLabel(text, "實際結果");

                    CollectScreenshots(p.Inline, screenshots);
                    pendingLabel = text;
                    break;
                }
                case ListBlock list when expectSteps:
                    steps.AddRange(ListItems(list));
                    expectSteps = false;
                    break;
                case Table:
                    break;
                case QuoteBlock quote:
                {
                    var qt = BlockText(quote);
                    var ev = Regex.Match(qt, @"evidence/(\S+)");
                    if (ev.Success && apiCalls.Count > 0)
                        apiCalls[^1] = apiCalls[^1] with { EvidenceFileName = ev.Groups[1].Value };
                    break;
                }
                case CodeBlock code:
                {
                    var codeText = GetCodeText(code);
                    var label = pendingLabel ?? "";
                    if (label.Contains("請求"))
                    {
                        pendingRequestCode = codeText;
                    }
                    else if (label.Contains("回應"))
                    {
                        var (method, url, headers) = pendingRequestCode != null
                            ? ParseRequestBlock(pendingRequestCode)
                            : ("", "", new Dictionary<string, string>());
                        var http = Regex.Match(label, @"HTTP\s*(\d+)");
                        var status2 = http.Success ? int.Parse(http.Groups[1].Value) : 0;
                        apiCalls.Add(new ApiCall(method, url, headers, status2, codeText, null));
                        pendingRequestCode = null;
                    }
                    break;
                }
            }
        }

        // 請求 code block 後若無對應「回應」段，仍保留請求資訊
        if (pendingRequestCode != null)
        {
            var (method, url, headers) = ParseRequestBlock(pendingRequestCode);
            apiCalls.Add(new ApiCall(method, url, headers, 0, "", null));
        }

        return new DetailItem(number, title, status, steps, expected, actual, apiCalls, screenshots);
    }

    private static (string Method, string Url, Dictionary<string, string> Headers) ParseRequestBlock(string code)
    {
        var headers = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var urlParts = new List<string>();
        bool inHeaders = false;

        foreach (var raw in code.Replace("\r", "").Split('\n'))
        {
            var line = raw.Trim();
            if (line.Length == 0) continue;
            if (line.Equals("Headers:", StringComparison.OrdinalIgnoreCase)) { inHeaders = true; continue; }
            if (inHeaders)
            {
                var idx = line.IndexOf(':');
                if (idx > 0) headers[line[..idx].Trim()] = line[(idx + 1)..].Trim();
            }
            else
            {
                urlParts.Add(line);
            }
        }

        var joined = string.Concat(urlParts);
        var space = joined.IndexOf(' ');
        if (space < 0) return ("", joined, headers);
        return (joined[..space], joined[(space + 1)..], headers);
    }

    // ── 待處理事項 ──────────────────────────────────────────────
    private static List<PendingItem> ExtractPending(MarkdownDocument doc)
    {
        var items = new List<PendingItem>();
        var table = FindFirstTable(SectionBlocks(doc, "待處理事項"));
        if (table == null) return items;

        foreach (var row in DataRows(table))
        {
            // # / 驗收條件 / 狀態 / 建議處理方式
            if (row.Count < 4) continue;
            int.TryParse(row[0].Trim(), out var num);
            items.Add(new PendingItem(num, row[1].Trim(), ParseStatusIcon(row[2]), row[3].Trim()));
        }
        return items;
    }

    // ── 附錄版本紀錄 ────────────────────────────────────────────
    private static List<AppendixVersionEntry> ExtractAppendixVersions(MarkdownDocument doc)
    {
        var versions = new List<AppendixVersionEntry>();
        var table = FindFirstTable(SectionBlocks(doc, "版本紀錄"));
        if (table == null) return versions;

        foreach (var row in DataRows(table))
        {
            if (row.Count < 3) continue;
            versions.Add(new AppendixVersionEntry(row[0].Trim(), row[1].Trim(), row[2].Trim()));
        }
        return versions;
    }

    private static DetailStatus ParseStatusIcon(string text)
    {
        if (text.Contains("✅") || text.Contains("通過") && !text.Contains("未通過")) return DetailStatus.Pass;
        if (text.Contains("❌") || text.Contains("未通過")) return DetailStatus.Fail;
        if (text.Contains("⚠") || text.Contains("警告")) return DetailStatus.Warn;
        if (text.Contains("🚧") || text.Contains("前置阻擋") || text.Contains("BLOCKED")) return DetailStatus.Blocked;
        if (text.Contains("⏭") || text.Contains("略過")) return DetailStatus.Skip;
        if (text.Contains("🔍") || text.Contains("👤") || text.Contains("待人工確認")) return DetailStatus.Manual;
        return DetailStatus.Manual;
    }

    // ════════════════════ Markdig helpers ════════════════════

    // 回傳指定標題之後、到下一個同層或更高層標題之前的所有 block
    private static List<Block> SectionBlocks(MarkdownDocument doc, string headingText)
    {
        var result = new List<Block>();
        int matchLevel = -1;
        bool collecting = false;

        foreach (var block in doc)
        {
            if (block is HeadingBlock h)
            {
                var text = GetInlineText(h.Inline).Trim();
                if (collecting && h.Level <= matchLevel) break;
                if (!collecting && text == headingText)
                {
                    collecting = true;
                    matchLevel = h.Level;
                    continue;
                }
            }
            if (collecting) result.Add(block);
        }
        return result;
    }

    // 將一段 block 依指定層級的標題切成 (heading 文字, body blocks)
    private static List<(string Heading, List<Block> Body)> SplitByHeading(List<Block> blocks, int level)
    {
        var groups = new List<(string, List<Block>)>();
        string? currentHeading = null;
        List<Block>? current = null;

        foreach (var b in blocks)
        {
            if (b is HeadingBlock h && h.Level == level)
            {
                if (currentHeading != null) groups.Add((currentHeading, current!));
                currentHeading = GetInlineText(h.Inline).Trim();
                current = new List<Block>();
            }
            else
            {
                current?.Add(b);
            }
        }
        if (currentHeading != null) groups.Add((currentHeading, current!));
        return groups;
    }

    private static Table? FindFirstTable(IEnumerable<Block> blocks)
        => blocks.OfType<Table>().FirstOrDefault();

    // 2 欄 key/value 表 → dict（跳過表頭列）
    private static Dictionary<string, string> TableToKeyValue(Table? table)
    {
        var map = new Dictionary<string, string>();
        if (table == null) return map;
        foreach (var row in DataRows(table))
            if (row.Count >= 2) map[row[0].Trim()] = row[1].Trim();
        return map;
    }

    // 表格資料列（跳過表頭），每列回傳各 cell 文字
    private static IEnumerable<List<string>> DataRows(Table table)
    {
        bool first = true;
        foreach (var rowObj in table)
        {
            if (rowObj is not TableRow row) continue;
            if (first || row.IsHeader) { first = false; continue; }
            var cells = new List<string>();
            foreach (var cellObj in row)
                if (cellObj is TableCell cell) cells.Add(BlockText(cell));
            yield return cells;
        }
    }

    private static List<string> ListItems(ListBlock list)
    {
        var items = new List<string>();
        foreach (var itemObj in list)
        {
            if (itemObj is not ListItemBlock li) continue;
            var sb = new StringBuilder();
            foreach (var b in li)
                if (b is ParagraphBlock p) sb.Append(GetInlineText(p.Inline));
            items.Add(sb.ToString().Trim());
        }
        return items;
    }

    private static void CollectScreenshots(ContainerInline? inline, List<string> sink)
    {
        if (inline == null) return;
        foreach (var child in inline)
        {
            if (child is LinkInline link && link.IsImage && link.Url != null)
                sink.Add(link.Url);
            if (child is ContainerInline container)
                CollectScreenshots(container, sink);
        }
    }

    private static string StripLabel(string text, string label)
    {
        var rest = text.Length > label.Length ? text[label.Length..] : "";
        return rest.TrimStart('：', ':', ' ').Trim();
    }

    // 任意 block 的純文字（段落 / 表格 cell / 引用）
    private static string BlockText(Block block)
    {
        var sb = new StringBuilder();
        switch (block)
        {
            case LeafBlock leaf when leaf.Inline != null:
                sb.Append(GetInlineText(leaf.Inline));
                break;
            case ContainerBlock container:
                foreach (var child in container)
                {
                    if (sb.Length > 0) sb.Append(' ');
                    sb.Append(BlockText(child));
                }
                break;
        }
        return sb.ToString().Trim();
    }

    private static string GetCodeText(CodeBlock code)
    {
        var sb = new StringBuilder();
        var lines = code.Lines.Lines;
        for (int i = 0; i < code.Lines.Count; i++)
            sb.AppendLine(lines[i].Slice.ToString());
        return sb.ToString().TrimEnd('\n');
    }

    private static string GetInlineText(Inline? inline)
    {
        var sb = new StringBuilder();
        Walk(inline, sb);
        return sb.ToString();
    }

    private static void Walk(Inline? inline, StringBuilder sb)
    {
        switch (inline)
        {
            case null:
                return;
            case LiteralInline lit:
                sb.Append(lit.Content.ToString());
                break;
            case CodeInline code:
                sb.Append(code.Content);
                break;
            case LineBreakInline:
                sb.Append(' ');
                break;
            case LinkInline { IsImage: true }:
                break; // 圖片 alt 不計入文字
            case ContainerInline container:
                foreach (var child in container) Walk(child, sb);
                break;
        }
    }
}
