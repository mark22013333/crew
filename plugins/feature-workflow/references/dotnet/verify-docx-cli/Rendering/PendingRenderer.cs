using DocumentFormat.OpenXml.Wordprocessing;
using FeatureWorkflow.VerifyDocxCli.Markdown;
using FeatureWorkflow.VerifyDocxCli.Styles;

namespace FeatureWorkflow.VerifyDocxCli.Rendering;

public sealed class PendingRenderer
{
    private readonly IBrandStyle _style;
    public PendingRenderer(IBrandStyle style) { _style = style; }

    public void Render(Body body, IReadOnlyList<PendingItem> items)
    {
        body.AppendChild(ParagraphBuilder.Heading("待處理事項", "Heading1"));
        var rows = new List<string[]> { new[] { "#", "驗收條件", "狀態", "建議處理方式" } };
        foreach (var p in items)
            rows.Add(new[] { p.Number.ToString(), p.Title, StatusToText(p.Status), p.Suggestion });
        body.AppendChild(TableBuilder.BuildSimple(rows.ToArray(), _style));
    }

    private static string StatusToText(DetailStatus s) => s switch
    {
        DetailStatus.Pass => "通過",
        DetailStatus.Fail => "未通過",
        DetailStatus.Warn => "警告",
        DetailStatus.Blocked => "前置阻擋",
        DetailStatus.Skip => "略過",
        DetailStatus.Manual => "待人工確認",
        _ => s.ToString()
    };
}
