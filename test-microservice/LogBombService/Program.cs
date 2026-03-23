using Exceptionless;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddExceptionless(config =>
{
    config.ApiKey = builder.Configuration["Exceptionless:ApiKey"] ?? "YOUR_API_KEY";
    config.ServerUrl = builder.Configuration["Exceptionless:ServerUrl"] ?? "http://localhost:5200";
});

builder.Services.AddOpenApi();

var app = builder.Build();

app.UseExceptionless();

if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
}

// Sağlık kontrolü
app.MapGet("/health", () => Results.Ok(new { status = "healthy", timestamp = DateTime.UtcNow }));

// Tek bir hata fırlat
app.MapPost("/fire", () =>
{
    try
    {
        throw new InvalidOperationException("Test hatası - tek atış");
    }
    catch (Exception ex)
    {
        ex.ToExceptionless()
            .AddTags("test", "single")
            .Submit();

        return Results.Ok(new { message = "1 hata gönderildi" });
    }
});

// Aynı hatadan N adet fırlat (duplicate/flood testi)
app.MapPost("/flood", (int? count) =>
{
    var total = count ?? 1000;

    for (var i = 0; i < total; i++)
    {
        try
        {
            throw new ApplicationException($"Flood test hatası #{i + 1}");
        }
        catch (Exception ex)
        {
            ex.ToExceptionless()
                .AddTags("flood", "load-test")
                .SetProperty("iteration", i + 1)
                .Submit();
        }
    }

    return Results.Ok(new { message = $"{total} hata gönderildi", total });
});

// Farklı türde hatalar fırlat (gruplama testi)
app.MapPost("/mixed", (int? count) =>
{
    var total = count ?? 100;
    var errorTypes = new (string Message, string Tag)[]
    {
        ("NullReferenceException: Object reference not set", "null-ref"),
        ("TimeoutException: Veritabanı bağlantı zaman aşımı", "timeout"),
        ("HttpRequestException: Üçüncü parti API yanıt vermiyor", "http-error"),
        ("ArgumentException: Geçersiz parametre değeri", "arg-error"),
        ("UnauthorizedAccessException: Yetkilendirme hatası", "auth-error"),
    };

    for (var i = 0; i < total; i++)
    {
        var (message, tag) = errorTypes[i % errorTypes.Length];
        try
        {
            throw new Exception(message);
        }
        catch (Exception ex)
        {
            ex.ToExceptionless()
                .AddTags("mixed", tag)
                .SetProperty("iteration", i + 1)
                .Submit();
        }
    }

    return Results.Ok(new { message = $"{total} karışık hata gönderildi", total });
});

// Log seviyesi testi (info, warning, error karışık)
app.MapPost("/log-levels", (int? count) =>
{
    var total = count ?? 500;
    var client = ExceptionlessClient.Default;

    for (var i = 0; i < total; i++)
    {
        switch (i % 3)
        {
            case 0:
                client.CreateLog("LogBombService", $"Info log #{i + 1}", "Info")
                    .AddTags("log-level-test")
                    .Submit();
                break;
            case 1:
                client.CreateLog("LogBombService", $"Warning log #{i + 1}", "Warn")
                    .AddTags("log-level-test")
                    .Submit();
                break;
            case 2:
                client.CreateLog("LogBombService", $"Error log #{i + 1}", "Error")
                    .AddTags("log-level-test")
                    .Submit();
                break;
        }
    }

    return Results.Ok(new { message = $"{total} log gönderildi (info/warn/error karışık)", total });
});

// Client konfigürasyonunu göster
app.MapGet("/stats", () =>
{
    var client = ExceptionlessClient.Default;
    return Results.Ok(new
    {
        configuration = new
        {
            apiKey = client.Configuration.ApiKey,
            serverUrl = client.Configuration.ServerUrl,
        },
        timestamp = DateTime.UtcNow
    });
});

app.Run();
