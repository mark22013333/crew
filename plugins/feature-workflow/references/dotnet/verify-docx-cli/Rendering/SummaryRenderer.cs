using DocumentFormat.OpenXml.Wordprocessing;
using FeatureWorkflow.VerifyDocxCli.Markdown;
using FeatureWorkflow.VerifyDocxCli.Styles;

namespace FeatureWorkflow.VerifyDocxCli.Rendering;

public sealed class SummaryRenderer
{
    private readonly IBrandStyle _style;
    public SummaryRenderer(IBrandStyle style) { _style = style; }

    public void Render(Body body, SummaryStats s)
    {
        body.AppendChild(ParagraphBuilder.Heading("驗收摘要", "Heading1"));
        body.AppendChild(TableBuilder.BuildSimple(new[]
        {
            new[] { "狀態", "數量" },
            new[] { "通過",       s.Pass.ToString() },
            new[] { "未通過",     s.Fail.ToString() },
            new[] { "警告",       s.Warn.ToString() },
            new[] { "前置阻擋",   s.Blocked.ToString() },
            new[] { "略過",       s.Skip.ToString() },
            new[] { "待人工確認", s.Manual.ToString() },
        }, _style));

        body.AppendChild(new Paragraph(
            ParagraphBuilder.TextRun($"結論：{s.Conclusion}", new RunProperties(new Bold()))));
    }
}
