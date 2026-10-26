# Record

```json
{
  "source": "agent",
  "format": "jac",
  "class": "function",
  "task_type": "farm",
  "fp": "kinged007_dragonapp__app_modules_shlink_schemas_py::ShlinkDomainPostPatch",
  "origin_file": "farm_dataset.jsonl",
  "origin_id": "kinged007_dragonapp__app_modules_shlink_schemas_py::ShlinkDomainPostPatch",
  "verification": "check+behavioral",
  "n_tokens": 564,
  "n_answer_tokens": 130
}
```

## SYSTEM

```
You are an expert AI assistant specializing in the jac programming language.
```

## USER

Implement the CRUD walkers for the 'ShlinkDomainPostPatch' node in the schema below. Output the walkers only.

```jac
node DeviceRedirects {
    has android: str | None = None;
    has ios: str | None = None;
    has desktop: str | None = None;
}

node ShortLinkMeta {
    has valid_since: str | None = None;
    has valid_until: str | None = None;
    has max_visits: int | None = None;
}

node ShortLinkVisitsSummary {
    has total: int = 0;
    has non_bots: int = 0;
    has bots: int = 0;
}

node ShortLinkVisitLocation {
    has country_code: str | None = None;
    has country_name: str | None = None;
    has latitude: float | None = None;
    has longitude: float | None = None;
    has region_name: str | None = None;
    has timezone: str | None = None;
    has city_name: str | None = None;
    has is_empty: bool = True;
}

node ShortLinkRequest {
    has url: str;
    has alias: str | None = None;
    has tags: list[str] | None = [];
    has domain: str | None = None;
    has forward_query_params: bool | None = False;
    has device_redirects: str | None = None;
    has expires_at: str | None = None;
}

node ShortLinkRedirect {
    has url: str;
    has response_code: int = 301;
}

node ShlinkDomainPostPatch {
    has domain: str | None = None;
    has is_active: bool | None = None;
}
```

## ASSISTANT

walker:pub create_ShlinkDomainPostPatch {
    has domain: str | None = None; has is_active: bool | None = None;
    can go with Root entry { new = here ++> ShlinkDomainPostPatch(domain=self.domain, is_active=self.is_active); report new; }
}
walker:pub list_ShlinkDomainPostPatch { can go with Root entry { report [-->[?:ShlinkDomainPostPatch]]; } }
walker:pub delete_ShlinkDomainPostPatch { can go with ShlinkDomainPostPatch entry { del here; report "deleted"; } }
