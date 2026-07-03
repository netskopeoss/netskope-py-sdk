# How to Build a Great Golang SDK

A comprehensive guide to building a world-class, publicly-released Go SDK — with specific attention to security product APIs like Netskope's. This document synthesizes patterns from aws-sdk-go-v2, google-cloud-go, stripe-go, go-github, hashicorp/vault-client-go, cloudflare-go, crowdstrike/gofalcon, zscaler-sdk-go, paloaltonetworks/sase-go, and elastic/go-elasticsearch.

---

## Table of Contents

1. [Philosophy: What Makes a Go SDK "Great"](#1-philosophy-what-makes-a-go-sdk-great)
2. [Package Structure & Repository Layout](#2-package-structure--repository-layout)
3. [Client Construction](#3-client-construction)
4. [Configuration Resolution](#4-configuration-resolution)
5. [HTTP Transport Layer](#5-http-transport-layer)
6. [Authentication & Token Management](#6-authentication--token-management)
7. [Error Handling](#7-error-handling)
8. [Pagination](#8-pagination)
9. [Retry & Rate Limiting](#9-retry--rate-limiting)
10. [Context Usage](#10-context-usage)
11. [Concurrency & Thread Safety](#11-concurrency--thread-safety)
12. [Logging & Debugging](#12-logging--debugging)
13. [Security-Specific Patterns](#13-security-specific-patterns)
14. [Testing Strategy](#14-testing-strategy)
15. [Documentation & Developer Experience](#15-documentation--developer-experience)
16. [Module Publishing & Versioning](#16-module-publishing--versioning)
17. [CI/CD & Quality Gates](#17-cicd--quality-gates)
18. [Naming Conventions](#18-naming-conventions)
19. [Terraform Provider Compatibility](#19-terraform-provider-compatibility)
20. [Python SDK vs Go SDK: Key Differences](#20-python-sdk-vs-go-sdk-key-differences)

---

## 1. Philosophy: What Makes a Go SDK "Great"

The Go community has strong opinions about what makes a library excellent. A great Go SDK embodies these principles:

**Minimal dependencies.** The Go proverb is "a little copying is better than a little dependency." Every dependency you add becomes a transitive dependency for all consumers. For an HTTP SDK, `net/http` from the standard library is often sufficient — no need for third-party HTTP clients. The best Go SDKs have zero or near-zero external dependencies.

**Small, stable API surface.** Use `internal/` packages aggressively to hide implementation details. Everything under `internal/` is inaccessible to external importers (enforced by the Go toolchain). This gives you freedom to refactor internals without breaking consumers.

**Zero-value usability.** Structs should do something reasonable at their zero value. `nil` slices and maps should be treated as empty. Optional parameters should use the functional options pattern so callers only specify what they need.

**No surprises.** Go developers expect explicit error returns (never panics), `context.Context` as the first parameter, goroutine safety on shared types, and silence by default (no logging unless opted in).

**Documentation is code.** In Go, godoc comments *are* the documentation. They render on pkg.go.dev automatically. Testable `Example` functions serve as both documentation and regression tests. There is no separate documentation site to maintain.

---

## 2. Package Structure & Repository Layout

Three dominant patterns exist across major Go SDKs. For a mid-sized SDK like Netskope's, **package-per-resource with a root client** provides the best balance:

```
github.com/netskope/netskope-go/
├── go.mod
├── go.sum
├── LICENSE                          # Apache 2.0 (recommended for vendor SDKs)
├── CHANGELOG.md
├── README.md
├── doc.go                           # Package-level documentation
├── client.go                        # NewClient, Client struct, functional options
├── client_options.go                # WithTenant(), WithAPIToken(), etc.
├── errors.go                        # Error types and sentinel errors
│
├── alerts/                          # One package per API resource namespace
│   ├── alerts.go                    # AlertsService type, List/Get methods
│   ├── alerts_test.go
│   └── models.go                    # Alert, AlertSeverity, etc.
│
├── events/
│   ├── events.go
│   └── models.go
│
├── incidents/
├── scim/
├── publishers/
├── privateapps/
├── steering/
├── urllists/
│
├── internal/                        # Hidden from consumers
│   ├── transport/                   # HTTP transport, auth injection, retry
│   │   ├── transport.go
│   │   ├── auth.go                  # Token RoundTripper
│   │   ├── retry.go                 # Retry with backoff
│   │   └── ratelimit.go            # Client-side rate limiting
│   ├── pagination/                  # Paginator implementations
│   └── validate/                    # Tenant validation, ID validation, SSRF checks
│
├── examples/                        # Runnable example programs
│   ├── list-alerts/main.go
│   ├── scim-sync/main.go
│   └── url-lists/main.go
│
└── .github/
    └── workflows/
        ├── ci.yml
        ├── integration.yml
        └── release.yml
```

### Key decisions

- **No `pkg/` directory.** This was a pattern in early Go projects but is now widely considered unnecessary. The top-level package should be importable directly.
- **`internal/` for machinery.** Transport, retry, pagination, validation — all internals. Consumers never import these.
- **One package per resource.** Each resource namespace (alerts, events, SCIM) gets its own package with co-located models. This keeps pkg.go.dev browsable and avoids a single package with hundreds of types.
- **Root package for the client.** `netskope.NewClient(...)` is the entry point. Resource services are exposed as fields: `client.Alerts`, `client.Events`, etc.

### Reference SDKs

| SDK | Structure | Notes |
|-----|-----------|-------|
| cloudflare-go | Package-per-resource with root client | Closest to recommended pattern |
| go-github | Single flat package | Works but unwieldy at scale (~1800 lines in github.go) |
| aws-sdk-go-v2 | Deeply nested, service-per-module | Too complex for a single-product SDK |
| vault-client-go | Root client with namespace fields | Clean: `client.Auth`, `client.Secrets`, `client.System` |

---

## 3. Client Construction

Use the **functional options pattern** — the dominant convention in modern Go SDKs. It is extensible without breaking changes, self-documenting, and supports sensible defaults.

### Pattern

```go
// Option configures the Netskope client.
type Option func(*config) error

// NewClient creates a new Netskope API client.
// The tenant and API token are resolved from explicit options,
// then environment variables (NETSKOPE_TENANT, NETSKOPE_API_TOKEN).
func NewClient(opts ...Option) (*Client, error) {
    cfg := defaultConfig()
    for _, opt := range opts {
        if err := opt(&cfg); err != nil {
            return nil, err
        }
    }
    if err := cfg.validate(); err != nil {
        return nil, err
    }
    return newClient(cfg)
}
```

### Key principles

- **Options return `error`** for validation during construction (vault-client-go pattern). This catches misconfigurations early with clear messages like `"request timeout must not be negative"`.
- **Constructor returns `(*Client, error)`** — never panic on bad input.
- **Required parameters can be positional** (stripe-go makes the API key positional: `NewClient(key, opts...)`), but for Netskope where tenant + token can be auto-resolved from env vars, all-options works well.
- **`defaultConfig()` provides sensible defaults**: 30s timeout, 3 retries, exponential backoff, User-Agent with SDK version.
- **Config struct is unexported** (`config`, not `Config`) — consumers interact only through `With*` functions, not by constructing config directly.

### Common options

```go
func WithTenant(tenant string) Option          // Override tenant domain
func WithAPIToken(token string) Option         // Override API token
func WithHTTPClient(c *http.Client) Option     // Custom HTTP client
func WithBaseURL(url string) Option            // Override base URL (testing)
func WithRetryMax(n int) Option                // Max retry attempts
func WithTimeout(d time.Duration) Option       // Request timeout
func WithLogger(l *slog.Logger) Option         // Structured logger
func WithUserAgent(ua string) Option           // Custom User-Agent suffix
```

### Per-request options

Following cloudflare-go and go-github, support per-request option overrides on individual method calls:

```go
type RequestOption func(*http.Request)

alerts, err := client.Alerts.List(ctx, alerts.ListParams{...},
    netskope.WithRequestHeader("X-Custom", "value"),
)
```

---

## 4. Configuration Resolution

Implement a **credential chain** (boto3-style), matching the existing Python SDK's pattern:

```
1. Explicit options       → WithTenant("..."), WithAPIToken("...")
2. Environment variables  → NETSKOPE_TENANT, NETSKOPE_API_TOKEN
3. (Future: config file)  → ~/.netskope/config.yaml
```

### Best practices

- **Explicit always wins.** Environment variables are only checked for fields not set via options.
- **Document the chain clearly.** Developers need to understand where credentials come from.
- **Validate eagerly.** Tenant domain validation (must end in `.goskope.com`, `.netskope.com`, or `.boomskope.com`) and SSRF prevention (block IP addresses) happen at construction time, not first request.
- **Support `allow_custom_tenant`** for internal/dev environments that use non-standard domains.

### Reference: How competitors do it

| SDK | Chain | Notes |
|-----|-------|-------|
| Zscaler | Explicit → env vars → YAML config file | Most layered, uses `envconfig` for struct-tag parsing |
| Vault | Explicit → env vars (with `env` struct tags) | Reflection-based env parsing |
| CrowdStrike | Explicit only | No env var reading — pushes to caller |
| Palo Alto | Explicit → env vars (opt-in) → JSON auth file | `CheckEnvironment bool` must be enabled |

---

## 5. HTTP Transport Layer

### Architecture: Composable RoundTripper Chains

The standard Go pattern for client middleware is composable `http.RoundTripper` decoration ("tripperwares"):

```
Logging → Auth → Rate Limit → Retry → http.DefaultTransport
```

Each layer wraps the next, adding its concern. Ordering matters:
- **Logging** is outermost — sees all requests including retries
- **Auth** injects tokens after logging (so tokens can be redacted in logs)
- **Rate limiting** prevents sending too many requests
- **Retry** wraps the base transport to retry on transient failures

### Key principles

- **Never replace `http.DefaultTransport` entirely.** Always wrap it to inherit connection pooling, keep-alive, HTTP/2, TLS defaults, and proxy support.
- **Never mutate the original `*http.Request` in `RoundTrip`.** Always clone first with `req.Clone(req.Context())`. The `http.RoundTripper` contract explicitly forbids mutation (go-github PR #805).
- **Accept a custom `*http.Client` via options** for consumers who need custom TLS, proxies, or transport configuration. Fall back to a configured default.
- **Increase `MaxIdleConnsPerHost`** from the default of 2 — for a single-API SDK, most connections go to the same host.

### Using `net/http` vs third-party clients

**Use `net/http`.** The standard library's HTTP client is production-grade, well-maintained, and adds zero dependencies. The Go community strongly prefers it for libraries. `httpx` (Python) features like async support are unnecessary in Go since goroutines handle concurrency natively.

### Reference: Transport patterns

| SDK | Pattern | Notes |
|-----|---------|-------|
| go-github | Auth via RoundTripper wrapping | Clean separation of auth from business logic |
| CrowdStrike | `TransportDecorator func(http.RoundTripper) http.RoundTripper` | Allows consumers to inject custom middleware |
| Palo Alto SCM-Go | `JWTRefreshTransport` → `LoggingRoundTripper` | Layered wrapping |
| Kubernetes client-go | Chain of RoundTrippers for impersonation, auth, TLS, logging | Most sophisticated real-world example |

---

## 6. Authentication & Token Management

### API Token Injection

For Netskope's API token auth, use an `http.RoundTripper` that injects the token header transparently:

```go
type authTransport struct {
    token string
    base  http.RoundTripper
}

func (t *authTransport) RoundTrip(req *http.Request) (*http.Response, error) {
    req = req.Clone(req.Context())
    req.Header.Set("Netskope-Api-Token", t.token)
    return t.base.RoundTrip(req)
}
```

### Secret handling

- Store the token in an **unexported field** on the client or transport.
- Implement `String()` on any type that holds secrets to prevent accidental logging: return `"[REDACTED]"`, not the actual value.
- Never log tokens at any log level by default. If a debug mode dumps HTTP headers, redact `Authorization` and `Netskope-Api-Token` headers.

### OAuth2 / Token refresh (future consideration)

If Netskope ever supports OAuth2 flows, the Palo Alto SCM-Go pattern is cleanest: a `JWTRefreshTransport` that is itself an `http.RoundTripper`, transparently refreshing the token before it expires. This makes token lifecycle invisible to all resource-level code.

CrowdStrike uses `golang.org/x/oauth2/clientcredentials` which also handles automatic refresh.

---

## 7. Error Handling

### Error hierarchy

Define typed error structs that support `errors.Is` and `errors.As`:

```go
// Sentinel errors for errors.Is checks
var (
    ErrAuthentication = errors.New("netskope: authentication failed")
    ErrForbidden      = errors.New("netskope: forbidden")
    ErrNotFound       = errors.New("netskope: resource not found")
    ErrRateLimit      = errors.New("netskope: rate limit exceeded")
    ErrServer         = errors.New("netskope: server error")
)

// APIError is returned for non-2xx HTTP responses.
type APIError struct {
    StatusCode int
    RequestID  string
    Message    string
    Err        error  // underlying sentinel for errors.Is
}

func (e *APIError) Error() string {
    return fmt.Sprintf("netskope: %s %d (request_id=%s): %s",
        http.StatusText(e.StatusCode), e.StatusCode, e.RequestID, e.Message)
}

func (e *APIError) Unwrap() error { return e.Err }
```

### Key principles

- **Structured, inspectable errors.** Include HTTP status code, request ID, and the error message from the API response. Developers should never see just `"request failed"`.
- **Actionable messages.** Stripe's Go SDK is praised for errors like `"Invalid API key provided. Check that your API key is correct and that you are using the right mode (test vs live)."` Include guidance, not just symptoms.
- **`errors.Is` for category checks**, `errors.As` for extracting details:

```go
// Category check
if errors.Is(err, netskope.ErrRateLimit) { ... }

// Detail extraction
var apiErr *netskope.APIError
if errors.As(err, &apiErr) {
    log.Printf("status=%d request_id=%s", apiErr.StatusCode, apiErr.RequestID)
}
```

- **Never panic.** Every error path returns `error`. This is non-negotiable in Go SDKs.
- **Wrap with context** using `fmt.Errorf("operation: %w", err)` so the error chain is preserved.
- **Helper functions** for common checks (vault-client-go pattern):

```go
func IsErrorStatus(err error, status int) bool {
    var apiErr *APIError
    if errors.As(err, &apiErr) {
        return apiErr.StatusCode == status
    }
    return false
}
```

### Reference SDKs

| SDK | Error Pattern | Strengths |
|-----|---------------|-----------|
| go-github | Typed structs: `ErrorResponse`, `RateLimitError`, `AbuseRateLimitError` | Most thorough, includes `Is()` |
| vault-client-go | `ResponseError` + `IsErrorStatus()` helper | Clean `errors.As` usage |
| aws-sdk-go-v2 | Generated per-error-code types | Fine-grained but heavy |
| stripe-go | `*Error` with `Unwrap()` and typed `ErrorCode` constants | Good chain support |

---

## 8. Pagination

### Go 1.23+ iterator pattern (recommended)

Go 1.23 introduced `iter.Seq2` and range-over-func, which provides the most idiomatic pagination in modern Go:

```go
func (s *AlertsService) List(ctx context.Context, params ListParams) iter.Seq2[*Alert, error] {
    return func(yield func(*Alert, error) bool) {
        offset := 0
        for {
            page, err := s.fetchPage(ctx, params, offset)
            if err != nil {
                yield(nil, err)
                return
            }
            for _, item := range page.Items {
                if !yield(&item, nil) {
                    return  // consumer stopped iterating
                }
            }
            if !page.HasMore {
                return
            }
            offset += len(page.Items)
        }
    }
}

// Usage: native for-range
for alert, err := range client.Alerts.List(ctx, params) {
    if err != nil {
        log.Fatal(err)
    }
    process(alert)
}
```

### Convenience methods

Provide helpers alongside the iterator:

```go
// Collect all results into a slice (with optional max)
func Collect[T any](seq iter.Seq2[*T, error], max int) ([]*T, error)

// Get just the first result
func First[T any](seq iter.Seq2[*T, error]) (*T, error)
```

### SCIM pagination

SCIM (RFC 7644) uses `startIndex`/`count` instead of `offset`/`limit`. Implement a separate paginator that maps to the same `iter.Seq2` interface so consumers don't need to know the underlying pagination mechanism.

### Alternative: Google iterator pattern (for Go <1.23 support)

If supporting Go versions before 1.23, use the Google Cloud iterator pattern: a `*FooIterator` struct with `Next() (*Foo, error)` that returns `iterator.Done` when exhausted.

### Anti-pattern: Channel-based pagination

Do not use channels for pagination. They require goroutine management, make error handling awkward, risk goroutine leaks if consumers stop reading, and are overkill when concurrency is not needed. The Google Cloud iterator guidelines deliberately reject this pattern.

---

## 9. Retry & Rate Limiting

### Retry strategy

Implement exponential backoff with full jitter:

```
sleep = min(cap, base * 2^attempt) * random(0.5, 1.0)
```

"Full jitter" (from the AWS architecture blog) is the most effective at reducing contention.

### What to retry

| Retry | Don't Retry |
|-------|-------------|
| 429 (Rate Limit) | 400 (Bad Request) |
| 500 (Internal Server Error) | 401 (Unauthorized) |
| 502 (Bad Gateway) | 403 (Forbidden) |
| 503 (Service Unavailable) | 404 (Not Found) |
| 504 (Gateway Timeout) | 409 (Conflict) |
| Connection reset / DNS failures | 422 (Unprocessable) |
| Timeouts (with care) | |

### Retry-After header respect

Always respect `Retry-After` headers from the server, capped at a safety maximum (e.g., 300 seconds) to prevent indefinite waits.

### Body replay

The request body is consumed on first send. Either buffer it, use `http.Request.GetBody`, or wrap it in a seekable reader (hashicorp/go-retryablehttp pattern). This is critical for retrying POST/PUT requests.

### Context checking

Before each retry attempt, check `ctx.Err()` to bail out early if the caller has canceled:

```go
select {
case <-ctx.Done():
    return nil, ctx.Err()
case <-time.After(backoff):
}
```

### Client-side rate limiting

Use `golang.org/x/time/rate.Limiter` (token bucket algorithm) as a RoundTripper to throttle outgoing requests proactively. This is the one external dependency worth adding — it's a golang.org/x package (quasi-stdlib).

Zscaler's SDK implements per-service rate limiters with different limits for GET vs POST/PUT/DELETE, which is worth considering for endpoints with known rate limits.

### Reference: How competitors handle it

| SDK | Retry | Rate Limiting |
|-----|-------|---------------|
| vault-client-go | hashicorp/go-retryablehttp, configurable | `golang.org/x/time/rate.Limiter`, configurable via env var |
| CrowdStrike | OAuth2 library handles retry | Reactive only — reads `X-Ratelimit-Remaining` header |
| Zscaler | Custom retry loop | Per-service sliding window with method-aware limits |
| Elasticsearch | Configurable `RetryOnStatus`, `MaxRetries`, custom `Backoff` | None — relies on retry-on-429 |

---

## 10. Context Usage

**Every public method must accept `context.Context` as its first parameter.** This is non-negotiable in Go.

```go
func (s *AlertsService) Get(ctx context.Context, id string) (*Alert, error)
func (s *AlertsService) List(ctx context.Context, params ListParams) iter.Seq2[*Alert, error]
func (s *ScimUsersService) Create(ctx context.Context, user CreateUserParams) (*ScimUser, error)
```

### Rules

- Name it `ctx`, not `c` or `context`.
- Never store context in a struct — pass it through the call chain.
- Never pass `nil` — use `context.Background()` if unsure.
- Propagate through the entire call chain, including pagination (the context used to create the iterator governs all page fetches).
- Respect cancellation: check `ctx.Done()` in long-running operations (pagination, retry loops).

### Timeouts

- Set a default `http.Client.Timeout` (e.g., 30s) as a safety net.
- Allow per-request overrides via context: `ctx, cancel := context.WithTimeout(ctx, 10*time.Second)`.
- For retry loops, check `ctx.Err()` before each attempt so a single slow retry doesn't consume the entire budget.

---

## 11. Concurrency & Thread Safety

### Go eliminates the sync/async split

In Python, the Netskope SDK needs both `NetskopeClient` and `AsyncNetskopeClient`, two sets of resource classes, and two pagination types. **In Go, there is a single client.** Concurrency is the caller's responsibility:

```go
// Concurrent requests — caller controls concurrency
g, ctx := errgroup.WithContext(ctx)

var alerts []*alerts.Alert
g.Go(func() error {
    var err error
    alerts, err = netskope.Collect(client.Alerts.List(ctx, params), 0)
    return err
})

var events []*events.Event
g.Go(func() error {
    var err error
    events, err = netskope.Collect(client.Events.List(ctx, params), 0)
    return err
})

if err := g.Wait(); err != nil {
    log.Fatal(err)
}
```

### Thread safety guarantees

- The `*Client` must be safe for concurrent use from multiple goroutines. **Document this explicitly.**
- `*http.Client` is safe for concurrent use — this is inherited.
- Use `sync.Mutex` or `sync.RWMutex` for any mutable state (rate limiter counters, cached tokens).
- Prefer immutable config — set once at construction, never mutate after.
- **Never spawn internal goroutines** unless for well-documented background tasks (e.g., token refresh). Leaked goroutines are a serious bug in Go libraries.

### This cuts the codebase roughly in half

No dual sync/async implementations. One client, one set of resource services, one pagination implementation. This is one of the biggest advantages of porting to Go.

---

## 12. Logging & Debugging

### Use `log/slog` (Go 1.21+)

`log/slog` is the standard structured logging package. Modern Go SDKs should integrate with it.

```go
client, err := netskope.NewClient(
    netskope.WithLogger(slog.Default()),
)
```

### Principles

- **Silent by default.** No logging unless the consumer provides a logger. This is a strong Go convention.
- **Structured key-value pairs:**

```go
logger.Debug("request sent",
    "method", req.Method,
    "url", req.URL.String(),
    "duration_ms", elapsed.Milliseconds(),
)
```

- **Sensible log levels:**
  - `Debug` — request/response details, retry attempts, pagination progress
  - `Info` — high-level operations (client created, auth succeeded)
  - `Warn` — degraded behavior (rate limited, retry needed)
  - `Error` — failures that the SDK cannot recover from

- **Never log secrets.** Redact `Netskope-Api-Token` and `Authorization` headers in debug output. Palo Alto pango's pattern is excellent: a `LogCategorySensitive` bitmask flag that must be explicitly enabled to see sensitive data.

- **Request/response dumping** via `httputil.DumpRequestOut` / `DumpResponse` behind debug-level logging, with header redaction.

### Reference

| SDK | Logging | Notes |
|-----|---------|-------|
| Palo Alto pango | `log/slog` with category bitmask | Best modern approach, explicit `Sensitive` flag |
| CrowdStrike | `logrus` | Older standard, heavier dependency |
| Zscaler | Custom `Logger` interface with `Printf` | Minimal |
| AWS SDK v2 | Granular flags: `LogSigning`, `LogRetries`, `LogRequest` | Most configurable |

---

## 13. Security-Specific Patterns

These patterns are specific to security product SDKs and distinguish them from general-purpose API clients.

### Credential management

- **Store tokens in unexported fields.** Never expose raw credentials through the public API.
- **Implement `String()` / `GoString()` methods** that return `[REDACTED]` on any type holding secrets.
- **Support multiple auth mechanisms** (API token, OAuth2 client credentials, JWT/private key) — security teams use different auth in different contexts (CI/CD, automation, interactive).

### SSRF prevention

The existing Python SDK blocks IP addresses in tenant URLs — **keep this in the Go SDK**. None of the competing Go SDKs implement this, making it a differentiator for security-conscious consumers.

```go
// Validate tenant domain, reject IP addresses
func validateTenant(tenant string) error {
    if net.ParseIP(tenant) != nil {
        return fmt.Errorf("netskope: IP addresses not allowed as tenant (SSRF prevention): %s", tenant)
    }
    // Check allowed domain suffixes
    // ...
}
```

### TLS defaults

- **Default to TLS 1.2 minimum.** Vault's approach of using `go-cleanhttp` (HTTP clients that don't share state with `http.DefaultClient`) is the gold standard.
- **Consider certificate fingerprint support** (Elasticsearch pattern) for high-security deployments.
- **Expose TLS configuration** via options for mTLS, custom CA certs, and cert pinning.

### Input validation

- **Validate resource IDs** against `^[a-zA-Z0-9_\-]+$` before URL path insertion to prevent injection — carry this over from the Python SDK.
- **Validate tenant domains** at construction time, not first request.
- **Use fuzz testing** on all input validation functions (tenant parsing, ID validation, query parameter encoding) — these are security-critical paths.

### Audit logging without leaking secrets

Palo Alto pango's category-based logging with an explicit `Sensitive` flag is the pattern to follow. By default, log request metadata (method, URL, status, duration, request ID) but never headers or bodies that might contain tokens or PII.

### Reference: Security SDK comparison

| Concern | CrowdStrike | Zscaler | Palo Alto | Vault | Recommended |
|---------|-------------|---------|-----------|-------|-------------|
| Token storage | Struct fields | Config struct | RoundTripper | Mutex-protected string | Unexported field + RoundTripper |
| Secret redaction | Minimal | Manual `********` replacement | Bitmask-controlled | Minimal | slog + Sensitive category flag |
| SSRF prevention | Allowlisted cloud hosts | Vanity domain pattern | Hardcoded hosts | N/A | IP blocking + domain suffix check |
| TLS config | System defaults | System defaults | `SkipVerifyCertificate` | Full TLS config struct | TLS 1.2+ default, full config exposed |
| Token refresh | `golang.org/x/oauth2` | Manual expiry tracking | RoundTripper wrapper | Manual | RoundTripper wrapper |

---

## 14. Testing Strategy

### Test pyramid for an SDK

1. **Unit tests** (majority) — test each component in isolation: client construction, request building, response parsing, error handling, retry logic, pagination, validation.
2. **HTTP mock tests** — use `net/http/httptest.Server` to spin up local servers mimicking the API.
3. **Integration tests** — hit the real API with live credentials, gated behind build tags.

### Table-driven tests

The canonical Go testing pattern. Every major Go SDK uses them:

```go
tests := []struct {
    name     string
    input    string
    expected int
    wantErr  bool
}{
    {"valid input", "hello", 5, false},
    {"empty input", "", 0, true},
}
for _, tt := range tests {
    t.Run(tt.name, func(t *testing.T) {
        got, err := Func(tt.input)
        if (err != nil) != tt.wantErr {
            t.Errorf("wantErr=%v, got err=%v", tt.wantErr, err)
        }
        if got != tt.expected {
            t.Errorf("got %d, want %d", got, tt.expected)
        }
    })
}
```

### HTTP mocking with `httptest`

The base URL must be configurable via `WithBaseURL()` — this is required for testability.

```go
srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(http.StatusOK)
    fmt.Fprint(w, `{"data": [...]}`)
}))
defer srv.Close()

client, _ := netskope.NewClient(
    netskope.WithBaseURL(srv.URL),
    netskope.WithAPIToken("test-token"),
)
```

### Integration tests

Gate behind build tags:

```go
//go:build integration

func TestLiveAlertsList(t *testing.T) {
    client, err := netskope.NewClient() // reads from env vars
    // ...
}
```

Run with: `go test -tags=integration ./...`

### Race detection

**Always run tests with `-race` in CI.** This is non-negotiable for libraries. The SDK client will be used concurrently — race detection catches data races.

```bash
go test -race ./...
```

### Fuzz testing

Go's built-in fuzzing (Go 1.18+) is ideal for security-critical input validation:

```go
func FuzzValidateTenant(f *testing.F) {
    f.Add("example.goskope.com")
    f.Add("evil.example.com")
    f.Add("")
    f.Add("http://192.168.1.1")

    f.Fuzz(func(t *testing.T, input string) {
        _, _ = validateTenant(input)  // must never panic
    })
}
```

Fuzz these paths: tenant validation, resource ID validation, JSON response parsing, query parameter encoding.

### What to use for assertions

- **Prefer stdlib `testing` package** — zero test dependencies.
- **`github.com/google/go-cmp`** is the one widely accepted test dependency for comparing complex structs (used by Google Cloud, Kubernetes). Use `cmp.Diff()` for clear failure output.
- **Avoid `testify`** in public libraries — it adds transitive dependencies for consumers who vendor.

### Interface for consumer testing

While the SDK should not define interfaces for every service (let consumers define their own), consider providing a `ClientInterface` or individual service interfaces so consumers can mock the SDK in their own tests without HTTP-level mocking.

---

## 15. Documentation & Developer Experience

### pkg.go.dev is the documentation

Go documentation is generated from code comments. Optimize for pkg.go.dev:

- **Package-level `doc.go`** with `// Package netskope provides ...` overview.
- **Every exported identifier** gets a doc comment starting with its name: `// Client manages communication with the Netskope API.`
- **Link related types** with `[TypeName]` bracket syntax (Go 1.19+).

### Testable examples

These are uniquely powerful in Go — they render on pkg.go.dev and are compiled/run by `go test`:

```go
func ExampleNewClient() {
    client, err := netskope.NewClient(
        netskope.WithTenant("example.goskope.com"),
        netskope.WithAPIToken(os.Getenv("NETSKOPE_API_TOKEN")),
    )
    if err != nil {
        log.Fatal(err)
    }
    defer client.Close()

    for alert, err := range client.Alerts.List(context.Background(), alerts.ListParams{}) {
        if err != nil {
            log.Fatal(err)
        }
        fmt.Println(alert.Name)
    }
}
```

Write `Example` functions for every major operation. They are both documentation and regression tests.

### README structure

1. One-line description
2. `go get` installation command
3. Quick start: a complete, copy-pasteable code block that creates a client and makes one API call
4. Authentication: env vars and explicit configuration
5. Common operations: 3-5 usage examples
6. Error handling: how to inspect errors with `errors.Is` / `errors.As`
7. Links to pkg.go.dev, examples directory, contributing guide
8. Badges: Go Reference, Go Report Card, CI status, license

**Do not duplicate API docs in the README** — that's what pkg.go.dev is for.

### Error messages are documentation

When a developer hits an error, the message is their primary guidance. Make errors actionable:

```
netskope: authentication failed (401, request_id=req_abc123): invalid API token.
Check that NETSKOPE_API_TOKEN is set correctly and has not expired.
```

Not:

```
request failed: 401
```

---

## 16. Module Publishing & Versioning

### Module path

```
github.com/netskope/netskope-go
```

Standard naming — matches the repository URL. No vanity import path needed initially.

### Versioning strategy

- **Start at `v0.x.x`** to allow API iteration without stability commitments.
- **Tag `v1.0.0`** only when the API is stable and battle-tested.
- **Semantic versioning:** `v1.2.3` format. Tags prefixed with `v`.
- **Once tagged and published, versions are immutable.** The Go module proxy caches permanently. If you tag a bad release, publish a new patch — you cannot retag.

### Backward compatibility

After v1.0.0:
- **Safe:** Adding new functions, types, methods, struct fields, option functions.
- **Breaking:** Removing/renaming exports, changing signatures, adding methods to interfaces.
- **Deprecation:** Use `// Deprecated: Use X instead.` comments (recognized by pkg.go.dev, staticcheck, IDEs). Keep deprecated functions working.

### Dependencies

**Aim for zero or minimal external dependencies.** Acceptable dependencies:

- `golang.org/x/time/rate` — rate limiting (quasi-stdlib)
- `golang.org/x/oauth2` — if OAuth2 flows are needed

Avoid everything else if possible. Use `net/http`, `encoding/json`, `log/slog`, `errors` from stdlib.

### Release process

1. Ensure tests pass, `go mod tidy` is clean, `go vet ./...` passes
2. Update `CHANGELOG.md`
3. Tag: `git tag v1.2.3 && git push origin v1.2.3`
4. The Go module proxy picks it up automatically (usually within minutes)
5. pkg.go.dev indexes it shortly after
6. Create a GitHub Release with changelog notes

### Minimum Go version

**Support the two most recent Go minor versions** (the Go team's own policy). Set the `go` directive in `go.mod` accordingly. Test both versions in CI.

For a new SDK in 2026, `go 1.23` is a reasonable minimum — this gives access to `iter.Seq2` (range-over-func), `log/slog`, and generics.

---

## 17. CI/CD & Quality Gates

### GitHub Actions workflow

```yaml
# .github/workflows/ci.yml
strategy:
  matrix:
    go-version: ['1.23', '1.24']
    os: [ubuntu-latest, macos-latest]
```

### Required CI jobs

| Job | Command | Purpose |
|-----|---------|---------|
| test | `go test -race -coverprofile=coverage.out ./...` | Unit tests with race detection |
| lint | `golangci-lint run` | Static analysis |
| build | `go build ./...` | Compilation check |
| mod-tidy | `go mod tidy && git diff --exit-code go.mod go.sum` | Ensure go.mod is clean |
| vuln | `govulncheck ./...` | Vulnerability scanning |

### golangci-lint configuration

Essential linters for an SDK library:

| Linter | Why |
|--------|-----|
| `govet` | Catches subtle bugs (printf mismatches, mutex copying) |
| `staticcheck` | Best single linter — unused code, deprecated APIs, impossible conditions |
| `errcheck` | Libraries MUST handle all errors |
| `gosec` | Security issues — critical for SDKs handling auth tokens |
| `bodyclose` | Ensures HTTP response bodies are closed |
| `noctx` | Ensures HTTP requests use context |
| `revive` | Exported function docs, naming conventions |
| `exhaustive` | Switch statements on enums cover all cases |
| `misspell` | Typos in comments and strings (public API docs) |
| `gofumpt` | Stricter formatting |

### Code coverage

- **Target 70-80%+.** Focus on: client construction, request building, response parsing, error handling, retry, pagination.
- Track trends via Codecov or Coveralls (with PR comments).
- **Do not fail CI on coverage thresholds** — they cause friction and gaming.

### Integration tests

Run on a separate workflow (scheduled or manual trigger) with live API credentials stored as GitHub Secrets.

---

## 18. Naming Conventions

### Packages

- Short, lowercase, single-word when possible: `alerts`, `events`, `scim`.
- No `util`, `common`, `base` — these are code smells in Go.
- Avoid stutter: `alerts.AlertsService` → `alerts.Service`. The package name provides context.

### Types

- Services: `Service` (not `AlertsService` inside the `alerts` package).
- Models: `Alert`, `Event`, `ScimUser` — noun, exported.
- Params: `ListParams`, `CreateParams` — operation + "Params".
- Errors: `APIError`, `RateLimitError` — cause + "Error".

### Methods

- CRUD: `Get`, `List`, `Create`, `Update`, `Delete`.
- Not `GetAlert` on an alerts service — just `Get`.
- Method signatures: `(ctx, params/id, ...opts) (result, error)`.

### Acronyms

Go convention: all caps for acronyms: `URL`, `HTTP`, `API`, `ID`, `DNS`, `SCIM`, `SSRF`.
Not `Url`, `Http`, `Api`, `Id`.

### JSON struct tags

Map API field names to Go-idiomatic names:

```go
type Alert struct {
    ID          string    `json:"_id"`
    AlertName   string    `json:"alert_name"`
    Severity    string    `json:"severity_level"`
    Timestamp   time.Time `json:"timestamp"`
}
```

---

## 19. Terraform Provider Compatibility

Security SDKs are frequently consumed by Terraform providers. Design with this in mind:

- **CRUD operations must be synchronous** — Terraform waits for completion.
- **Read operations must handle "not found" cleanly** — return `(nil, nil)` not an error, so Terraform's `Exists` checks work.
- **`context.Context` on all operations** — Terraform passes cancellation contexts.
- **Retry and rate limiting handled inside the SDK** — the Terraform provider should not need its own retry logic.
- **Composable User-Agent** — Terraform providers append their version info:

```go
func WithUserAgentExtra(extra string) Option
// Results in: "netskope-go/1.0.0 terraform-provider-netskope/0.5.0"
```

### Reference: Terraform-consumed SDKs

| SDK | Terraform Provider | Notes |
|-----|-------------------|-------|
| zscaler-sdk-go | terraform-provider-zia, terraform-provider-zpa | Direct backend |
| pango (Palo Alto) | terraform-provider-panos | "The underlying library for the PAN-OS Terraform provider" |
| Palo Alto SCM-Go | terraform-provider-scm | Factory function pattern per resource domain |

---

## 20. Python SDK vs Go SDK: Key Differences

For developers familiar with the existing Netskope Python SDK, here are the fundamental shifts:

| Aspect | Python SDK | Go SDK |
|--------|-----------|--------|
| **Client types** | `NetskopeClient` + `AsyncNetskopeClient` | Single `Client` — goroutines handle concurrency |
| **Resource types** | Sync + Async variants of each | Single implementation per resource |
| **Pagination types** | Sync + Async iterators | Single `iter.Seq2` implementation |
| **Codebase size** | ~2x (dual sync/async) | ~1x (single implementation) |
| **Models** | Pydantic v2 with runtime validation | Plain structs with JSON tags; compile-time type safety |
| **Immutability** | `frozen=True` on models | Mutable by default (idiomatic Go) |
| **Extra fields** | `extra="allow"` catches unknown fields | `encoding/json` silently ignores unknown fields by default |
| **Error handling** | Exception hierarchy with try/except | Explicit `error` returns with `errors.Is`/`errors.As` |
| **Secret handling** | Pydantic `SecretStr` | Unexported field + `String()` returning `[REDACTED]` |
| **HTTP client** | httpx (external dep) | `net/http` (stdlib, zero deps) |
| **Timestamp handling** | `TimestampMixin` auto-converts epoch → datetime | Custom `UnmarshalJSON` on a `Timestamp` type or `time.Time` |
| **Config resolution** | `NetskopeConfig.resolve()` | Logic in `NewClient()` with functional options |
| **Testing** | `respx` for HTTP mocking | `net/http/httptest` (stdlib) |
| **Dependencies** | httpx, pydantic + transitive | Zero or minimal (stdlib-first) |

### What carries over directly

- Configuration resolution chain (explicit → env vars)
- SSRF prevention (IP blocking, domain suffix allowlist)
- Resource ID validation regex
- Response envelope handling per resource
- Retry strategy (exponential backoff with jitter, Retry-After respect)
- Error hierarchy mapping (401→Auth, 403→Forbidden, 404→NotFound, 429→RateLimit)
- Pagination safety limit (1000 pages max)
- Time parameter handling (`is not None` → `!= nil`)

### What changes fundamentally

- No async/sync split — single implementation of everything
- No runtime model validation — compile-time types + JSON tags
- No exception hierarchy — explicit error returns everywhere
- No dependency on an HTTP framework — stdlib `net/http`
- `context.Context` threading — new concept not present in the Python SDK
- Interface-based testability — consumers can mock without HTTP-level mocking

---

## Appendix: Recommended Reading

- [Effective Go](https://go.dev/doc/effective_go) — the foundational Go style guide
- [Go Code Review Comments](https://go.dev/wiki/CodeReviewComments) — common Go idioms
- [Go Client Library Best Practices](https://medium.com/@cep21/go-client-library-best-practices-83d877d604ca) — Jack Lindamood
- [Google Cloud Go Iterator Guidelines](https://github.com/googleapis/google-cloud-go/wiki/Iterator-Guidelines)
- [Functional Options for Friendly APIs](https://dave.cheney.net/2014/10/17/functional-options-for-friendly-apis) — Dave Cheney
- [Go Blog: Range Over Function Types](https://go.dev/blog/range-functions) — Go 1.23 iterators
- [Go Blog: Structured Logging with slog](https://go.dev/blog/slog) — Go 1.21 logging
- [Cloudflare: The Complete Guide to Go net/http Timeouts](https://blog.cloudflare.com/the-complete-guide-to-golang-net-http-timeouts/)
- [AWS Architecture Blog: Exponential Backoff and Jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)

### Go SDKs to study

| SDK | Why | Link |
|-----|-----|------|
| google/go-github | Gold standard for Go SDK design | github.com/google/go-github |
| aws-sdk-go-v2 | Most comprehensive middleware/retry | github.com/aws/aws-sdk-go-v2 |
| stripe-go | Best onboarding DX | github.com/stripe/stripe-go |
| vault-client-go | Clean functional options + error patterns | github.com/hashicorp/vault-client-go |
| cloudflare-go | Package-per-resource structure | github.com/cloudflare/cloudflare-go |
| crowdstrike/gofalcon | Security product patterns, event streaming | github.com/crowdstrike/gofalcon |
| zscaler-sdk-go | Security product, rate limiting, config chain | github.com/zscaler/zscaler-sdk-go |
