using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Wordprocessing;
using FeatureWorkflow.VerifyDocxCli.Markdown;
using FeatureWorkflow.VerifyDocxCli.Sanitization;
using FeatureWorkflow.VerifyDocxCli.Styles;

namespace FeatureWorkflow.VerifyDocxCli.Rendering;

public sealed class DetailRenderer
{
    private const long EmuPerInch = 914400L;
    private readonly MainDocumentPart _mainPart;
    private readonly IBrandStyle _style;
    private readonly DirectoryInfo? _screenshotsDir;
    private readonly DirectoryInfo? _evidenceDir;

    public DetailRenderer(MainDocumentPart mainPart, IBrandStyle style,
        DirectoryInfo? screenshotsDir, DirectoryInfo? evidenceDir)
    {
        _mainPart = mainPart;
        _style = style;
        _screenshotsDir = screenshotsDir;
        _evidenceDir = evidenceDir;
    }

    public void Render(Body body, IReadOnlyList<DetailItem> details)
    {
        body.AppendChild(ParagraphBuilder.Heading("驗收明細", "Heading1"));
        foreach (var d in details)
        {
            body.AppendChild(ParagraphBuilder.Heading($"驗收項目 {d.Number}：{d.Title}", "Heading2"));
            body.AppendChild(BuildResultParagraph(d.Status));

            if (d.HumanSteps.Count > 0)
            {
                body.AppendChild(BuildBoldLabel("操作步驟"));
                for (int i = 0; i < d.HumanSteps.Count; i++)
                    body.AppendChild(ParagraphBuilder.Body($"{i + 1}. {d.HumanSteps[i]}"));
            }

            if (!string.IsNullOrWhiteSpace(d.ExpectedResult))
                body.AppendChild(ParagraphBuilder.Body($"預期結果：{d.ExpectedResult}"));
            if (!string.IsNullOrWhiteSpace(d.ActualResult))
                body.AppendChild(ParagraphBuilder.Body($"實際結果：{d.ActualResult}"));

            foreach (var call in d.ApiCalls)
                BuildApiCallBlock(body, call);

            foreach (var path in d.ScreenshotPaths)
                BuildScreenshot(body, path);
        }
    }

    private Paragraph BuildResultParagraph(DetailStatus status)
    {
        var (text, color) = status switch
        {
            DetailStatus.Pass   => ("✅ 通過", BrandColors.StatusPass),
            DetailStatus.Fail   => ("❌ 未通過", BrandColors.StatusFail),
            DetailStatus.Warn   => ("⚠️ 警告", BrandColors.StatusWarn),
            DetailStatus.Blocked=> ("🚧 前置阻擋", BrandColors.StatusBlocked),
            DetailStatus.Skip   => ("⏭️ 略過", BrandColors.StatusSkip),
            DetailStatus.Manual => ("🔍 待人工確認", BrandColors.StatusManual),
            _ => ("待人工確認", BrandColors.StatusManual)
        };
        var rPr = new RunProperties(new Bold(), new Color { Val = color });
        return new Paragraph(ParagraphBuilder.TextRun($"結果：{text}", rPr));
    }

    private static Paragraph BuildBoldLabel(string text)
        => new Paragraph(ParagraphBuilder.TextRun(text, new RunProperties(new Bold())));

    private void BuildApiCallBlock(Body body, ApiCall call)
    {
        var maskedHeaders = SensitiveDataMasker.Mask(call.Headers);
        var headerLines = string.Join("\n", maskedHeaders.Select(kv => $"  {kv.Key}: {kv.Value}"));
        var requestText = $"請求：\n  {call.Method} {call.Url}".TrimEnd();
        if (headerLines.Length > 0) requestText += $"\nHeaders:\n{headerLines}";

        var responseLines = call.ResponseBody.Replace("\r", "").Split('\n');
        string responseText;
        if (call.ResponseBody.Length == 0)
        {
            responseText = "(無回應內容)";
        }
        else if (responseLines.Length <= 20)
        {
            responseText = call.ResponseBody;
        }
        else
        {
            var head = string.Join("\n", responseLines.Take(10));
            var tail = string.Join("\n", responseLines.TakeLast(10));
            var omitted = responseLines.Length - 20;
            responseText = $"{head}\n\n... （省略 {omitted} 行，共 {responseLines.Length} 行）\n\n{tail}";
            if (call.EvidenceFileName != null)
                responseText += $"\n\n> 完整回應請見：evidence/{call.EvidenceFileName}";
        }

        body.AppendChild(BuildBoldLabel("測試紀錄"));
        body.AppendChild(ParagraphBuilder.Code(requestText));
        body.AppendChild(ParagraphBuilder.Code($"回應（HTTP {call.HttpStatus}）：\n{responseText}"));
    }

    private void BuildScreenshot(Body body, string relativePath)
    {
        if (_screenshotsDir == null)
        {
            body.AppendChild(ParagraphBuilder.Body($"（截圖不可用：{relativePath}）"));
            return;
        }
        var fileName = Path.GetFileName(relativePath);
        var fullPath = Path.Combine(_screenshotsDir.FullName, fileName);
        if (!File.Exists(fullPath))
        {
            body.AppendChild(ParagraphBuilder.Body($"（截圖不可用：{relativePath}）"));
            return;
        }
        body.AppendChild(ImageInserter.InlineImage(_mainPart, fullPath, (long)(5.5 * EmuPerInch)));
    }
}
