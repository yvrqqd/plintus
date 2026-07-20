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
from plintus.rules.class_rules import ClassMethodBlankLines, ClassMethodOrder
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
    NoCatchBareException,
    NoSlottedDictAccess,
    RequireSlots,
)
from plintus.rules.graphql_rules import (
    BanAlternateGraphql,
    NoDaoInResolvers,
    ObserveLatencyOnResolvers,
)
from plintus.rules.import_order import ImportOrder
from plintus.rules.logging_rules import (
    AllowedLogLevels,
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
        ImportOrder(),
        CallArgOrder(),
        BannedCalls(),
        RequireDecorator(),
        ClassMethodOrder(),
        ClassMethodBlankLines(),
        # CBP logging
        LogMsgKeyword(),
        NoPrint(),
        NoBasicConfig(),
        NoNestedTagsExtra(),
        GetLoggerDunderName(),
        AllowedLogLevels(),
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
        NoCatchBareException(),
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
