"""Built-in rule pack."""

from __future__ import annotations

from plintus.api import Rule
from plintus.rules.async_rules import (
    AppRunnerHandleSignals,
    NoGetEventLoop,
    NoRequestsInAsync,
    NoToThread,
)
from plintus.rules.banned_calls import BannedCalls
from plintus.rules.call_order import CallArgOrder
from plintus.rules.config_rules import (
    NoOsEnviron,
    OneSettingsPerFile,
    SecretStrForSecrets,
    SettingsFieldAlias,
)
from plintus.rules.error_rules import (
    CopyrightHeader,
    DaoNoConnectClose,
    NoBareException,
    NoSlottedDictAccess,
    RequireSlots,
)
from plintus.rules.graphql_rules import (
    BanAlternateGraphql,
    NoDaoInResolvers,
    ObserveLatencyOnResolvers,
)
from plintus.rules.logging_rules import (
    GetLoggerDunderName,
    LogMsgKeyword,
    NoBasicConfig,
    NoNestedTagsExtra,
    NoPrint,
)
from plintus.rules.quotes import DictQuotes, MessageQuotes
from plintus.rules.require_decorator import RequireDecorator
from plintus.rules.s3_rules import NoGcInS3
from plintus.rules.sql_rules import NoFormatSql
from plintus.rules.wps import register_wps


def register() -> list[Rule]:
    return [
        DictQuotes(),
        MessageQuotes(),
        CallArgOrder(),
        BannedCalls(),
        RequireDecorator(),
        # CBP logging
        LogMsgKeyword(),
        NoPrint(),
        NoBasicConfig(),
        NoNestedTagsExtra(),
        GetLoggerDunderName(),
        # CBP async
        NoGetEventLoop(),
        NoToThread(),
        NoRequestsInAsync(),
        AppRunnerHandleSignals(),
        # CBP config
        NoOsEnviron(),
        SettingsFieldAlias(),
        SecretStrForSecrets(),
        OneSettingsPerFile(),
        # CBP errors / structure
        NoBareException(),
        DaoNoConnectClose(),
        RequireSlots(),
        CopyrightHeader(),
        NoSlottedDictAccess(),
        # CBP graphql / sql / s3
        BanAlternateGraphql(),
        ObserveLatencyOnResolvers(),
        NoDaoInResolvers(),
        NoFormatSql(),
        NoGcInS3(),
        # WPS (wemake-python-styleguide codes)
        *register_wps(),
    ]
