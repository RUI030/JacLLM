import os;
import from nodes.IntegrationConfig { IntegrationConfig }
import from nodes.Platform { Platform }
import from config { env_or, ensure_config, seed_demo_config, list_configs }
import from app_platform { bootstrap_platform, get_platform_overview }


test "env_or returns a non-empty variable or the fallback" {
    os.environ["REVDEV_UNIBANK_ENV_OR"] = "from-env";
    assert env_or("REVDEV_UNIBANK_ENV_OR", "fallback") == "from-env";
    os.environ["REVDEV_UNIBANK_ENV_OR"] = "";
    assert env_or("REVDEV_UNIBANK_ENV_OR", "fallback") == "fallback";
    os.environ.pop("REVDEV_UNIBANK_ENV_OR", None);
    assert env_or("REVDEV_UNIBANK_ENV_OR", "fallback") == "fallback";
}


test "ensure_config creates one config per provider and updates it in place" {
    first = ensure_config(
        provider="revdev-unibank-prov", label="First", api_key="key-1",
        rpc_url="https://revdev.example/rpc",
    );
    assert isinstance(first, IntegrationConfig);
    assert first.config_id == "revdev-unibank-prov_config";
    assert first.label == "First";
    assert first.api_key == "key-1";
    assert first.chain_id == "8453";
    assert first.mode == "test";
    assert first.enabled == True;

    second = ensure_config(provider="revdev-unibank-prov", label="Second", mode="live");
    assert jid(second) == jid(first);
    assert second.label == "Second";
    assert second.mode == "live";
    # Omitted arguments fall back to their defaults on update.
    assert second.api_key == "";
    assert second.rpc_url == "";

    matches = [c for c in list_configs() if c.provider == "revdev-unibank-prov"];
    assert len(matches) == 1;
    assert matches[0].label == "Second";
}


test "seed_demo_config seeds stripe, wallet_provider and rpc from env or fallbacks" {
    os.environ["STRIPE_SECRET_KEY"] = "sk_revdev_unibank";
    os.environ["APP_MODE"] = "revdev-mode";
    os.environ.pop("CHAIN_ID", None);
    os.environ.pop("DEFAULT_CHAIN", None);
    os.environ.pop("RPC_URL", None);

    configs = seed_demo_config();
    seed_demo_config();

    assert len(configs) == 3;
    assert [c.provider for c in configs] == ["stripe", "wallet_provider", "rpc"];
    assert [c.config_id for c in configs] == ["stripe_config", "wallet_provider_config", "rpc_config"];
    assert configs[0].label == "Stripe Checkout";
    assert configs[0].secret_key == "sk_revdev_unibank";
    assert configs[0].mode == "revdev-mode";
    assert configs[2].label == "Base RPC";
    assert configs[2].chain_id == "8453";
    assert configs[2].rpc_url == "https://FILL_ME_RPC_URL";

    providers = [c.provider for c in list_configs()];
    assert providers.count("stripe") == 1;
    assert providers.count("wallet_provider") == 1;
    assert providers.count("rpc") == 1;

    os.environ.pop("STRIPE_SECRET_KEY", None);
    os.environ.pop("APP_MODE", None);
}


test "bootstrap_platform reuses one Platform node and seeds the configs" {
    os.environ["PLATFORM_NAME"] = "revdev-unibank-platform";
    os.environ["APP_ENV"] = "revdev-staging";
    os.environ.pop("DEFAULT_CHAIN", None);

    first = bootstrap_platform();
    second = bootstrap_platform();

    assert first["platform_id"] == second["platform_id"];
    assert len([root-->][?:Platform]) == 1;
    platform = [root-->][?:Platform][0];
    assert first["platform_id"] == jid(platform);
    assert first["name"] == "revdev-unibank-platform";
    assert first["environment"] == "revdev-staging";
    assert first["default_chain"] == "base";
    assert first["config_count"] == 3;
    assert len(first["env_keys"]) == 15;
    assert first["env_keys"]["platform_name"] == "PLATFORM_NAME";
    assert first["env_keys"]["chain_id"] == "CHAIN_ID";

    os.environ.pop("PLATFORM_NAME", None);
    os.environ.pop("APP_ENV", None);
}


test "get_platform_overview reports the platform and counts root children" {
    os.environ["PLATFORM_NAME"] = "revdev-unibank-overview";
    os.environ.pop("DEFAULT_ASSET", None);
    boot = bootstrap_platform();
    overview = get_platform_overview();

    assert overview["platform_id"] == boot["platform_id"];
    assert overview["name"] == "revdev-unibank-overview";
    assert overview["default_asset"] == "USDC";
    # Every node directly under root counts: the Platform plus the three seeded configs at least.
    assert overview["merchant_count"] >= 4;
    assert overview["merchant_count"] == len([root-->]);
    assert "config_count" not in overview;

    os.environ.pop("PLATFORM_NAME", None);
}
