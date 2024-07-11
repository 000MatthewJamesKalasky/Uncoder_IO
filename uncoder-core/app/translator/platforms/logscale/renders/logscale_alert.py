"""
Uncoder IO Community Edition License
-----------------------------------------------------------------
Copyright (c) 2024 SOC Prime, Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-----------------------------------------------------------------
"""

import copy
import json
from typing import Optional

from app.translator.core.mapping import SourceMapping
from app.translator.core.models.platform_details import PlatformDetails
from app.translator.core.models.query_container import MetaInfoContainer
from app.translator.managers import render_manager
from app.translator.platforms.logscale.const import DEFAULT_LOGSCALE_ALERT, logscale_alert_details
from app.translator.platforms.logscale.mapping import LogScaleMappings, logscale_alert_mappings
from app.translator.platforms.logscale.renders.logscale import LogScaleFieldValueRender, LogScaleQueryRender
from app.translator.tools.utils import get_rule_description_str

_AUTOGENERATED_TEMPLATE = "Autogenerated Falcon LogScale Alert"


class LogScaleAlertFieldValueRender(LogScaleFieldValueRender):
    details: PlatformDetails = logscale_alert_details


@render_manager.register
class LogScaleAlertRender(LogScaleQueryRender):
    details: PlatformDetails = logscale_alert_details
    mappings: LogScaleMappings = logscale_alert_mappings
    or_token = "or"
    field_value_render = LogScaleAlertFieldValueRender(or_token=or_token)

    def finalize_query(
        self,
        prefix: str,
        query: str,
        functions: str,
        meta_info: Optional[MetaInfoContainer] = None,
        source_mapping: Optional[SourceMapping] = None,  # noqa: ARG002
        not_supported_functions: Optional[list] = None,
        unmapped_fields: Optional[list[str]] = None,
        *args,  # noqa: ARG002
        **kwargs,  # noqa: ARG002
    ) -> str:
        query = super().finalize_query(prefix=prefix, query=query, functions=functions)
        rule = copy.deepcopy(DEFAULT_LOGSCALE_ALERT)
        rule["query"]["queryString"] = query
        rule["name"] = meta_info.title or _AUTOGENERATED_TEMPLATE
        mitre_attack = []
        if meta_info.mitre_attack:
            mitre_attack = sorted([f"ATTACK.{i['tactic']}" for i in meta_info.mitre_attack.get("tactics", [])])
            mitre_attack.extend(
                sorted([f"ATTACK.{i['technique_id']}" for i in meta_info.mitre_attack.get("techniques", [])])
            )
        rule["description"] = get_rule_description_str(
            description=meta_info.description or _AUTOGENERATED_TEMPLATE,
            license_=meta_info.license,
            author=meta_info.author,
            mitre_attack=mitre_attack,
        )

        rule_str = json.dumps(rule, indent=4, sort_keys=False)
        rule_str = self.wrap_with_unmapped_fields(rule_str, unmapped_fields)
        return self.wrap_with_not_supported_functions(rule_str, not_supported_functions)
