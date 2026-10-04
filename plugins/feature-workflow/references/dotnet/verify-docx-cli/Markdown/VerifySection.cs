namespace FeatureWorkflow.VerifyDocxCli.Markdown;

// 從 --cover JSON 解出來
public record CoverInfo(
    string Project, string Feature, string Author,
    string Date, string Company, string Version);

// 每條驗收明細
public record DetailItem(
    int Number,
    string Title,
    DetailStatus Status,
    List<string> HumanSteps,        // **操作步驟** 後的 ordered list
    string ExpectedResult,
    string ActualResult,
    List<ApiCall> ApiCalls,         // **測試紀錄** 後的 請求/回應 code block
    List<string> ScreenshotPaths);  // ![desc](screenshots/...)

public enum DetailStatus { Pass, Fail, Warn, Blocked, Skip, Manual }

public record ApiCall(
    string Method, string Url, Dictionary<string, string> Headers,
    int HttpStatus, string ResponseBody, string? EvidenceFileName);

// 驗收摘要
public record SummaryStats(int Pass, int Fail, int Warn, int Blocked, int Skip, int Manual, string Conclusion);

// 待處理事項
public record PendingItem(int Number, string Title, DetailStatus Status, string Suggestion);

// 測試環境
public record EnvInfo(
    string Url, string Browser, string Role,
    string DataDescription, string Prerequisites);

// 附錄版本紀錄
public record AppendixVersionEntry(string Date, string Version, string Description);

// 整份 verify.md 解析結果
public record VerifyReport(
    CoverInfo Cover,
    EnvInfo Env,
    SummaryStats Summary,
    List<DetailItem> Details,
    List<PendingItem> Pending,
    List<AppendixVersionEntry> Versions);
