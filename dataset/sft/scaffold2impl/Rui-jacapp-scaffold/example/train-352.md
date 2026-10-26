# Record

```json
{
  "source": "code",
  "format": "repo",
  "class": "fullstack",
  "task_type": "scaffold2impl",
  "fp": "JacHackA2Tech/adithyan2020__ClaimSureAI::main.jac"
}
```

## SYSTEM

```
You are a Jac programming assistant in a chat interface. Put all Jac code in your reply inside a ```jac fenced code block.
```

## USER

Given the Jac scaffold below (declarations only, bodies replaced with `{ ... }`), write the full implementation. Keep the existing structure and docstrings.

```jac
import from services.claims {
    ClaimView, RiskResult, RiskFactor, Neighbor, DenialExtraction, AppealView, AuditView,
    seed_demo, list_claims, check_claim, get_risk, mark_denied, start_appeal,
    extract_denial_letter, open_upload_appeal, get_appeal, save_letter, override_review,
    approve_appeal, reject_appeal, simulate_payer_response, list_audit
}

cl {
    import ".styles.global.css";
    import from "@jac/runtime" { Router, Routes, Route }
    import from .components.ui.sonner_toast { Toaster }
    import from .components.AppLayout { AppLayout }
    import from .components.Dashboard { Dashboard }
    import from .components.ClaimIntake { ClaimIntake }
    import from .components.RiskDetail { RiskDetail }
    import from .components.UploadDenial { UploadDenial }
    import from .components.AppealTracker { AppealTracker }
    import from .components.AuditLog { AuditLog }

    def:pub app() -> JsxElement { ... }
}
```

## ASSISTANT

```jac
import from services.claims {
    ClaimView, RiskResult, RiskFactor, Neighbor, DenialExtraction, AppealView, AuditView,
    seed_demo, list_claims, check_claim, get_risk, mark_denied, start_appeal,
    extract_denial_letter, open_upload_appeal, get_appeal, save_letter, override_review,
    approve_appeal, reject_appeal, simulate_payer_response, list_audit
}

cl {
    import ".styles.global.css";
    import from "@jac/runtime" { Router, Routes, Route }
    import from .components.ui.sonner_toast { Toaster }
    import from .components.AppLayout { AppLayout }
    import from .components.Dashboard { Dashboard }
    import from .components.ClaimIntake { ClaimIntake }
    import from .components.RiskDetail { RiskDetail }
    import from .components.UploadDenial { UploadDenial }
    import from .components.AppealTracker { AppealTracker }
    import from .components.AuditLog { AuditLog }

    def:pub app() -> JsxElement {
        return <Router>
            <Routes>
                <Route element={<AppLayout />}>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/claims/new" element={<ClaimIntake />} />
                    <Route path="/claims/:id/risk" element={<RiskDetail />} />
                    <Route path="/upload" element={<UploadDenial />} />
                    <Route path="/appeals/:id" element={<AppealTracker />} />
                    <Route path="/audit" element={<AuditLog />} />
                    <Route path="*" element={<Dashboard />} />
                </Route>
            </Routes>
            <Toaster position="top-right" />
        </Router>;
    }
}
```
