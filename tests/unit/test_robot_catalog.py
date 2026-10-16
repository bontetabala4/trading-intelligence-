from core.integration.robot_catalog import (
    IntegrationStatus,
    list_known_trading_platforms,
)


def test_known_platform_catalogue_is_informational_and_not_enabled_for_execution():
    platforms = list_known_trading_platforms()

    assert {platform.identifier for platform in platforms} == {
        "metatrader_ea",
        "freqtrade",
        "hummingbot",
        "quantconnect_lean",
        "cryptohopper",
    }
    assert all(platform.status != "EXECUTION_ENABLED" for platform in platforms)
    assert any(platform.status == IntegrationStatus.RESEARCH_ONLY for platform in platforms)
