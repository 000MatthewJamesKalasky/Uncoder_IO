"""
Uncoder IO Commercial Edition License
-----------------------------------------------------------------
Copyright (c) 2024 SOC Prime, Inc.

This file is part of the Uncoder IO Commercial Edition ("CE") and is
licensed under the Uncoder IO Non-Commercial License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://github.com/UncoderIO/UncoderIO/blob/main/LICENSE

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-----------------------------------------------------------------
"""
import copy
import math
from datetime import timedelta
from typing import Optional

import yaml

from app.translator.core.context_vars import return_only_first_query_ctx_var, wrap_query_with_meta_info_ctx_var
from app.translator.core.exceptions.render import BaseRenderException
from app.translator.core.models.platform_details import PlatformDetails
from app.translator.core.models.query_container import RawQueryContainer, TokenizedQueryContainer
from app.translator.core.render import PlatformQueryRender, QueryRender
from app.translator.managers import RenderManager, render_manager
from app.translator.platforms.microsoft.const import MICROSOFT_SENTINEL_QUERY_DETAILS
from app.translator.platforms.microsoft.mapping import microsoft_sentinel_query_mappings
from app.translator.platforms.roota.const import ROOTA_RULE_DETAILS, ROOTA_RULE_TEMPLATE
from app.translator.platforms.sigma.const import SIGMA_RULE_DETAILS
from app.translator.platforms.sigma.mapping import sigma_rule_mappings

_AUTOGENERATED_TEMPLATE = "Autogenerated Roota Rule"


class IndentedListDumper(yaml.Dumper):
    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:  # noqa: ARG002
        return super().increase_indent(flow, False)


@render_manager.register
class RootARender(PlatformQueryRender):
    details: PlatformDetails = PlatformDetails(**ROOTA_RULE_DETAILS)
    render_manager: RenderManager = render_manager
    mappings = microsoft_sentinel_query_mappings

    @staticmethod
    def __render_timeframe(timeframe: timedelta) -> str:
        total_seconds = timeframe.total_seconds()

        week_ = 7  # days
        day_ = 24  # hours
        hour_ = 60  # minutes
        minute_ = 60  # seconds

        if total_seconds >= week_ * day_ * hour_ * minute_:
            timeframe_value = math.ceil(total_seconds / (week_ * day_ * hour_ * minute_))
            timeframe_unit = "w"
        elif total_seconds >= day_ * hour_ * minute_:
            timeframe_value = math.ceil(total_seconds / (day_ * hour_ * minute_))
            timeframe_unit = "d"
        elif total_seconds >= hour_ * minute_:
            timeframe_value = math.ceil(total_seconds / (hour_ * minute_))
            timeframe_unit = "h"
        elif total_seconds >= minute_:
            timeframe_value = math.ceil(total_seconds / minute_)
            timeframe_unit = "m"
        else:
            timeframe_value = math.ceil(total_seconds)
            timeframe_unit = "s"
        return f"{timeframe_value}{timeframe_unit}"

    @staticmethod
    def __normalize_log_source(log_source: dict) -> dict:
        prepared_log_source = {}
        for log_source_key, value in log_source.items():
            if isinstance(value, list):
                value = value[0]
            prepared_log_source[log_source_key] = value.lower()
        return prepared_log_source

    def __get_data_for_roota_render(
        self, raw_query_container: RawQueryContainer, tokenized_query_container: TokenizedQueryContainer
    ) -> tuple:
        if raw_query_container.language == SIGMA_RULE_DETAILS["platform_id"]:
            rule_query_language = MICROSOFT_SENTINEL_QUERY_DETAILS["platform_id"]
            prev_state_return_only_first_query_ctx_var = return_only_first_query_ctx_var.get()
            prev_state_wrap_query_with_meta_info_ctx_var = wrap_query_with_meta_info_ctx_var.get()
            return_only_first_query_ctx_var.set(True)
            wrap_query_with_meta_info_ctx_var.set(False)

            render: QueryRender = render_manager.get(rule_query_language)
            rule_query = render.generate(
                raw_query_container=raw_query_container, tokenized_query_container=tokenized_query_container
            )
            return_only_first_query_ctx_var.set(prev_state_return_only_first_query_ctx_var)
            wrap_query_with_meta_info_ctx_var.set(prev_state_wrap_query_with_meta_info_ctx_var)

            return (
                rule_query,
                rule_query_language,
                self.__normalize_log_source(log_source=tokenized_query_container.meta_info.parsed_logsources),
            )
        rule_query_language = raw_query_container.language.replace("rule", "query")
        rule_query = raw_query_container.query
        for source_mapping_id in tokenized_query_container.meta_info.source_mapping_ids:
            if source_mapping_id == "default":
                continue
            if logsources := self.__get_logsources_by_source_mapping_id(source_mapping_id=source_mapping_id):
                return rule_query, rule_query_language, self.__normalize_log_source(log_source=logsources)
        return rule_query, rule_query_language, {}

    @staticmethod
    def __get_logsources_by_source_mapping_id(source_mapping_id: str) -> Optional[dict]:
        if source_mapping := sigma_rule_mappings.get_source_mapping(source_mapping_id):
            return source_mapping.log_source_signature.log_sources

    def generate(
        self, raw_query_container: RawQueryContainer, tokenized_query_container: Optional[TokenizedQueryContainer]
    ) -> str:
        if not tokenized_query_container or not tokenized_query_container.meta_info:
            raise BaseRenderException("Meta info is required")
        rule_query, rule_query_language, rule_logsources = self.__get_data_for_roota_render(
            raw_query_container=raw_query_container, tokenized_query_container=tokenized_query_container
        )

        rule = copy.deepcopy(ROOTA_RULE_TEMPLATE)
        rule["name"] = tokenized_query_container.meta_info.title or _AUTOGENERATED_TEMPLATE
        rule["details"] = tokenized_query_container.meta_info.description or rule["details"]
        rule["author"] = tokenized_query_container.meta_info.author_str or rule["author"]
        rule["severity"] = tokenized_query_container.meta_info.severity or rule["severity"]
        rule["date"] = tokenized_query_container.meta_info.date
        rule["detection"]["language"] = rule_query_language
        rule["detection"]["body"] = rule_query
        rule["license"] = tokenized_query_container.meta_info.license
        rule["uuid"] = tokenized_query_container.meta_info.id
        rule["references"] = raw_query_container.meta_info.references or tokenized_query_container.meta_info.references
        rule["tags"] = raw_query_container.meta_info.tags or tokenized_query_container.meta_info.tags

        if tokenized_query_container.meta_info.raw_mitre_attack:
            rule["mitre-attack"] = tokenized_query_container.meta_info.raw_mitre_attack
        elif tokenized_query_container.meta_info.mitre_attack:
            techniques = [
                technique.technique_id.lower()
                for technique in tokenized_query_container.meta_info.mitre_attack.techniques
            ]
            tactics = [
                tactic.name.lower().replace(" ", "-")
                for tactic in tokenized_query_container.meta_info.mitre_attack.tactics
            ]
            rule["mitre-attack"] = techniques + tactics

        if tokenized_query_container.meta_info.timeframe:
            rule["correlation"] = {}
            rule["correlation"]["timeframe"] = self.__render_timeframe(tokenized_query_container.meta_info.timeframe)

        if rule_logsources:
            rule["logsource"] = rule_logsources

        return yaml.dump(rule, Dumper=IndentedListDumper, default_flow_style=False, sort_keys=False, indent=4)
