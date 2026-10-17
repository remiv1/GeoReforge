# Test report / Rapport de tests

## Sommaire / Table of contents

- [English](#english)
- [Français](#français)

## English

- Date: 26-10-17_17-07
- Result: PASSED
- Tests: 119 | Passed: 119 | Failed: 0 | Errors: 0 | Skipped: 0
- Duration: 88.69 s

### Results by test class

#### `tests.test_data_pipeline` - English

| Test | Result | Duration | Details |
| --- | --- | ---: | --- |
| `test_geo_forged_item_relationships_are_configured` | passed | 0.012 s | - |
| `test_mapper_loads_fields_and_classes_for_each_key` | passed | 0.000 s | - |
| `test_importer_builds_routes_and_extracts_shapefile_components` | passed | 0.003 s | - |
| `test_build_aggregates_keeps_source_name_and_ignores_incomplete_groups` | passed | 0.001 s | - |
| `test_injecter_selects_each_mapping_and_translates_classes` | passed | 0.002 s | - |
| `test_injecter_rejects_unknown_mapping_and_missing_source_class` | passed | 0.002 s | - |
| `test_injecter_does_not_repeat_repository_rollback_on_commit_failure` | passed | 0.000 s | - |
| `test_full_injection_persists_zones[sqlite]` | passed | 0.119 s | - |
| `test_full_injection_persists_zones[postgres]` | passed | 23.844 s | - |
| `test_full_injection_persists_zones[mysql]` | passed | 4.251 s | - |
| `test_full_injection_persists_zones[mariadb]` | passed | 1.324 s | - |

#### `tests.test_database` - English

| Test | Result | Duration | Details |
| --- | --- | ---: | --- |
| `test_sqlite_first_start_and_restart` | passed | 11.909 s | - |
| `test_missing_sqlite_directory_prevents_start` | passed | 0.714 s | - |
| `test_external_first_start_and_restart[postgres-TEST_POSTGRES_URL]` | passed | 10.454 s | - |
| `test_external_first_start_and_restart[mysql-TEST_MYSQL_URL]` | passed | 8.642 s | - |
| `test_external_first_start_and_restart[mariadb-TEST_MARIADB_URL]` | passed | 8.373 s | - |

#### `tests.test_zones_maker` - English

| Test | Result | Duration | Details |
| --- | --- | ---: | --- |
| `test_load_catalog_validates_and_returns_typed_datasets` | passed | 0.001 s | - |
| `test_build_config_preserves_selection_and_only_selected_mappings` | passed | 0.000 s | - |
| `test_validation_requires_mapping_for_every_selected_dataset` | passed | 0.000 s | - |
| `test_toml_serialization_round_trips` | passed | 0.001 s | - |
| `test_save_dated_copy_uses_date_and_never_overwrites` | passed | 0.001 s | - |
| `test_replace_mode_only_writes_the_explicit_target` | passed | 0.001 s | - |
| `test_resolve_existing_shapefile_does_not_download` | passed | 0.001 s | - |
| `test_resolve_missing_shapefile_downloads_only_selected_archive` | passed | 0.001 s | - |
| `test_resolve_physical_dataset_uses_natural_earth_archive_url[lakes]` | passed | 0.001 s | - |
| `test_resolve_physical_dataset_uses_natural_earth_archive_url[ocean]` | passed | 0.002 s | - |
| `test_resolve_rejects_archive_path_traversal` | passed | 0.001 s | - |

#### `tests.test_auth` - English

| Test | Result | Duration | Details |
| --- | --- | ---: | --- |
| `test_authenticated_modes_reject_default_or_short_secret[default_secret_key-internal]` | passed | 0.002 s | - |
| `test_authenticated_modes_reject_default_or_short_secret[default_secret_key-external]` | passed | 0.001 s | - |
| `test_authenticated_modes_reject_default_or_short_secret[xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx-internal]` | passed | 0.001 s | - |
| `test_authenticated_modes_reject_default_or_short_secret[xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx-external]` | passed | 0.001 s | - |
| `test_authenticated_modes_accept_long_secret[internal]` | passed | 0.001 s | - |
| `test_authenticated_modes_accept_long_secret[external]` | passed | 0.001 s | - |
| `test_none_mode_keeps_local_secret_defaults[default_secret_key]` | passed | 0.001 s | - |
| `test_none_mode_keeps_local_secret_defaults[short]` | passed | 0.001 s | - |
| `test_production_none_mode_requires_explicit_anonymous_access_opt_in` | passed | 0.001 s | - |
| `test_cookie_names_must_be_valid_and_distinct[session]` | passed | 0.001 s | - |
| `test_cookie_names_must_be_valid_and_distinct[]` | passed | 0.001 s | - |
| `test_cookie_names_must_be_valid_and_distinct[bad name]` | passed | 0.001 s | - |
| `test_cookie_names_must_be_valid_and_distinct[bad;name]` | passed | 0.001 s | - |
| `test_flask_cookie_settings_follow_secure_connection` | passed | 0.001 s | - |
| `test_flask_cookie_settings_reject_inconsistent_values` | passed | 0.002 s | - |
| `test_flask_session_cookie_has_secure_attributes_by_setting` | passed | 0.039 s | - |
| `test_secure_connection_rejects_http_except_health` | passed | 0.018 s | - |
| `test_local_http_remains_available_when_secure_connection_is_disabled` | passed | 0.017 s | - |
| `test_none_mode_exposes_virtual_identity_and_disables_login` | passed | 0.018 s | - |
| `test_internal_login_success_sets_auth_cookie_and_identity[False]` | passed | 0.170 s | - |
| `test_internal_login_success_sets_auth_cookie_and_identity[True]` | passed | 0.169 s | - |
| `test_internal_login_requires_csrf` | passed | 0.016 s | - |
| `test_internal_invalid_credentials_are_rejected[username-absent]` | passed | 0.161 s | - |
| `test_internal_invalid_credentials_are_rejected[password-absent]` | passed | 0.093 s | - |
| `test_internal_invalid_credentials_are_rejected[user-inconnu]` | passed | 0.162 s | - |
| `test_internal_invalid_credentials_are_rejected[mauvais-mot-de-passe]` | passed | 0.163 s | - |
| `test_failed_attempts_use_the_same_delay` | passed | 0.300 s | - |
| `test_lock_after_six_failures_success_resets_and_service_unlocks` | passed | 1.075 s | - |
| `test_unknown_user_does_not_create_persistent_failure_state` | passed | 1.425 s | - |
| `test_forced_login_requests_lock_the_known_account` | passed | 0.592 s | - |
| `test_simultaneous_failed_attempts_are_counted_atomically` | passed | 0.203 s | - |
| `test_group_access_respects_active_association` | passed | 0.170 s | - |
| `test_group_access_follows_role_hierarchy[user_groups0-ADMIN-200]` | passed | 0.017 s | - |
| `test_group_access_follows_role_hierarchy[user_groups1-EDITOR-200]` | passed | 0.016 s | - |
| `test_group_access_follows_role_hierarchy[user_groups2-VIEWER-200]` | passed | 0.016 s | - |
| `test_group_access_follows_role_hierarchy[user_groups3-ADMIN-403]` | passed | 0.017 s | - |
| `test_group_access_follows_role_hierarchy[user_groups4-VIEWER-200]` | passed | 0.016 s | - |
| `test_group_access_follows_role_hierarchy[user_groups5-EDITOR-403]` | passed | 0.016 s | - |
| `test_none_mode_virtual_admin_inherits_all_roles` | passed | 0.017 s | - |
| `test_user_crud_and_collisions_leave_session_usable` | passed | 0.230 s | - |
| `test_username_and_email_collisions_roll_back[username-duplique]` | passed | 0.220 s | - |
| `test_username_and_email_collisions_roll_back[email-duplique]` | passed | 0.221 s | - |
| `test_failed_user_update_rolls_back_all_field_changes` | passed | 0.152 s | - |
| `test_concurrent_external_provisioning_is_idempotent` | passed | 0.033 s | - |
| `test_admin_bootstrap_is_idempotent` | passed | 0.086 s | - |
| `test_admin_bootstrap_does_not_restore_removed_admin_group` | passed | 0.091 s | - |
| `test_admin_bootstrap_requires_password_only_when_creating_account` | passed | 0.011 s | - |
| `test_concurrent_admin_bootstrap_is_idempotent` | passed | 0.108 s | - |
| `test_password_change_and_disable_revoke_all_sessions` | passed | 0.155 s | - |
| `test_expired_session_is_rejected_and_deleted` | passed | 0.081 s | - |
| `test_password_is_absent_from_success_and_failure_logs` | passed | 0.231 s | - |
| `test_external_mode_callback_creates_session_and_maps_allowed_groups` | passed | 0.030 s | - |
| `test_external_callback_rejects_disabled_user_without_creating_session` | passed | 0.027 s | - |
| `test_user_provenance_is_persisted_and_external_identity_cannot_be_renamed` | passed | 0.089 s | - |
| `test_changing_auth_mode_purges_all_persisted_authentication_state` | passed | 0.173 s | - |
| `test_legacy_external_identity_is_completed_on_matching_callback` | passed | 0.019 s | - |
| `test_external_login_route_starts_redirect` | passed | 0.016 s | - |
| `test_oidc_callback_rejects_expected_authentication_errors[state-invalide]` | passed | 0.017 s | - |
| `test_oidc_callback_rejects_expected_authentication_errors[profil-invalide]` | passed | 0.017 s | - |
| `test_oidc_callback_rejects_expected_authentication_errors[claim-absent]` | passed | 0.017 s | - |
| `test_oidc_bad_signature_is_not_accepted` | passed | 0.018 s | - |
| `test_oidc_network_errors_are_unavailable_and_do_not_leak_details[connection-error]` | passed | 0.018 s | - |
| `test_oidc_network_errors_are_unavailable_and_do_not_leak_details[timeout]` | passed | 0.019 s | - |
| `test_auth_errors_are_json_and_auth_responses_are_not_cached` | passed | 0.018 s | - |
| `test_oidc_missing_subject_creates_no_user_or_session` | passed | 0.007 s | - |
| `test_internal_logout_requires_csrf_and_revokes_session` | passed | 0.167 s | - |

#### `tests.test_front` - English

| Test | Result | Duration | Details |
| --- | --- | ---: | --- |
| `test_privileged_markup_is_absent[False-VIEWER-forbidden0]` | passed | 0.317 s | - |
| `test_privileged_markup_is_absent[False-EDITOR-forbidden1]` | passed | 0.310 s | - |
| `test_privileged_markup_is_absent[True-VIEWER-forbidden0]` | passed | 0.306 s | - |
| `test_privileged_markup_is_absent[True-EDITOR-forbidden1]` | passed | 0.303 s | - |
| `test_viewer_cannot_call_privileged_routes[/builder]` | passed | 0.290 s | - |
| `test_viewer_cannot_call_privileged_routes[/builder/search]` | passed | 0.290 s | - |
| `test_viewer_cannot_call_privileged_routes[/sources]` | passed | 0.291 s | - |
| `test_viewer_cannot_call_privileged_routes[/administration]` | passed | 0.297 s | - |
| `test_preferences_are_persisted_and_scoped` | passed | 0.317 s | - |
| `test_preview_does_not_save_and_versions_are_immutable` | passed | 0.320 s | - |
| `test_builder_exposes_preview_and_create_actions` | passed | 0.302 s | - |
| `test_viewer_exports_versions[yaml-code:]` | passed | 0.301 s | - |
| `test_viewer_exports_versions[geojson-{]` | passed | 0.300 s | - |
| `test_viewer_exports_versions[gpkg-SQLite format 3]` | passed | 0.306 s | - |
| `test_viewer_exports_versions[shp-PK]` | passed | 0.305 s | - |
| `test_viewer_exports_versions[postgis-BEGIN;]` | passed | 0.298 s | - |
| `test_admin_can_delete_a_version_after_snapshot` | passed | 0.351 s | - |
| `test_catalog_snapshot_delete_and_restore_are_faithful_and_atomic` | passed | 0.355 s | - |
| `test_sources_require_confirmation_and_preserve_dependencies` | passed | 0.313 s | - |
| `test_toml_preview_only_adds_after_validation` | passed | 0.314 s | - |
| `test_yaml_roundtrip_and_invalid_input` | passed | 0.330 s | - |
| `test_mutations_require_csrf` | passed | 0.290 s | - |
| `test_invalid_toml_is_rejected_without_changes[{}]` | passed | 0.310 s | - |
| `test_invalid_toml_is_rejected_without_changes[source_path=12\ndata_family="incorrect"]` | passed | 0.296 s | - |
| `test_invalid_toml_is_rejected_without_changes[source_path="https://naturalearth.s3.amazonaws.com"\n[data_family]\ncultural="incorrect"]` | passed | 0.294 s | - |
| `test_preferences_follow_authentication_context` | passed | 0.297 s | - |

## Français

- Date : 26-10-17_17-07
- Résultat : RÉUSSI
- Tests : 119 | Réussis : 119 | Échecs : 0 | Erreurs : 0 | Ignorés : 0
- Durée : 88.69 s

### Résultats par classe de test

#### `tests.test_data_pipeline` - Français

| Test | Résultat | Durée | Détails |
| --- | --- | ---: | --- |
| `test_geo_forged_item_relationships_are_configured` | réussi | 0.012 s | - |
| `test_mapper_loads_fields_and_classes_for_each_key` | réussi | 0.000 s | - |
| `test_importer_builds_routes_and_extracts_shapefile_components` | réussi | 0.003 s | - |
| `test_build_aggregates_keeps_source_name_and_ignores_incomplete_groups` | réussi | 0.001 s | - |
| `test_injecter_selects_each_mapping_and_translates_classes` | réussi | 0.002 s | - |
| `test_injecter_rejects_unknown_mapping_and_missing_source_class` | réussi | 0.002 s | - |
| `test_injecter_does_not_repeat_repository_rollback_on_commit_failure` | réussi | 0.000 s | - |
| `test_full_injection_persists_zones[sqlite]` | réussi | 0.119 s | - |
| `test_full_injection_persists_zones[postgres]` | réussi | 23.844 s | - |
| `test_full_injection_persists_zones[mysql]` | réussi | 4.251 s | - |
| `test_full_injection_persists_zones[mariadb]` | réussi | 1.324 s | - |

#### `tests.test_database` - Français

| Test | Résultat | Durée | Détails |
| --- | --- | ---: | --- |
| `test_sqlite_first_start_and_restart` | réussi | 11.909 s | - |
| `test_missing_sqlite_directory_prevents_start` | réussi | 0.714 s | - |
| `test_external_first_start_and_restart[postgres-TEST_POSTGRES_URL]` | réussi | 10.454 s | - |
| `test_external_first_start_and_restart[mysql-TEST_MYSQL_URL]` | réussi | 8.642 s | - |
| `test_external_first_start_and_restart[mariadb-TEST_MARIADB_URL]` | réussi | 8.373 s | - |

#### `tests.test_zones_maker` - Français

| Test | Résultat | Durée | Détails |
| --- | --- | ---: | --- |
| `test_load_catalog_validates_and_returns_typed_datasets` | réussi | 0.001 s | - |
| `test_build_config_preserves_selection_and_only_selected_mappings` | réussi | 0.000 s | - |
| `test_validation_requires_mapping_for_every_selected_dataset` | réussi | 0.000 s | - |
| `test_toml_serialization_round_trips` | réussi | 0.001 s | - |
| `test_save_dated_copy_uses_date_and_never_overwrites` | réussi | 0.001 s | - |
| `test_replace_mode_only_writes_the_explicit_target` | réussi | 0.001 s | - |
| `test_resolve_existing_shapefile_does_not_download` | réussi | 0.001 s | - |
| `test_resolve_missing_shapefile_downloads_only_selected_archive` | réussi | 0.001 s | - |
| `test_resolve_physical_dataset_uses_natural_earth_archive_url[lakes]` | réussi | 0.001 s | - |
| `test_resolve_physical_dataset_uses_natural_earth_archive_url[ocean]` | réussi | 0.002 s | - |
| `test_resolve_rejects_archive_path_traversal` | réussi | 0.001 s | - |

#### `tests.test_auth` - Français

| Test | Résultat | Durée | Détails |
| --- | --- | ---: | --- |
| `test_authenticated_modes_reject_default_or_short_secret[default_secret_key-internal]` | réussi | 0.002 s | - |
| `test_authenticated_modes_reject_default_or_short_secret[default_secret_key-external]` | réussi | 0.001 s | - |
| `test_authenticated_modes_reject_default_or_short_secret[xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx-internal]` | réussi | 0.001 s | - |
| `test_authenticated_modes_reject_default_or_short_secret[xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx-external]` | réussi | 0.001 s | - |
| `test_authenticated_modes_accept_long_secret[internal]` | réussi | 0.001 s | - |
| `test_authenticated_modes_accept_long_secret[external]` | réussi | 0.001 s | - |
| `test_none_mode_keeps_local_secret_defaults[default_secret_key]` | réussi | 0.001 s | - |
| `test_none_mode_keeps_local_secret_defaults[short]` | réussi | 0.001 s | - |
| `test_production_none_mode_requires_explicit_anonymous_access_opt_in` | réussi | 0.001 s | - |
| `test_cookie_names_must_be_valid_and_distinct[session]` | réussi | 0.001 s | - |
| `test_cookie_names_must_be_valid_and_distinct[]` | réussi | 0.001 s | - |
| `test_cookie_names_must_be_valid_and_distinct[bad name]` | réussi | 0.001 s | - |
| `test_cookie_names_must_be_valid_and_distinct[bad;name]` | réussi | 0.001 s | - |
| `test_flask_cookie_settings_follow_secure_connection` | réussi | 0.001 s | - |
| `test_flask_cookie_settings_reject_inconsistent_values` | réussi | 0.002 s | - |
| `test_flask_session_cookie_has_secure_attributes_by_setting` | réussi | 0.039 s | - |
| `test_secure_connection_rejects_http_except_health` | réussi | 0.018 s | - |
| `test_local_http_remains_available_when_secure_connection_is_disabled` | réussi | 0.017 s | - |
| `test_none_mode_exposes_virtual_identity_and_disables_login` | réussi | 0.018 s | - |
| `test_internal_login_success_sets_auth_cookie_and_identity[False]` | réussi | 0.170 s | - |
| `test_internal_login_success_sets_auth_cookie_and_identity[True]` | réussi | 0.169 s | - |
| `test_internal_login_requires_csrf` | réussi | 0.016 s | - |
| `test_internal_invalid_credentials_are_rejected[username-absent]` | réussi | 0.161 s | - |
| `test_internal_invalid_credentials_are_rejected[password-absent]` | réussi | 0.093 s | - |
| `test_internal_invalid_credentials_are_rejected[user-inconnu]` | réussi | 0.162 s | - |
| `test_internal_invalid_credentials_are_rejected[mauvais-mot-de-passe]` | réussi | 0.163 s | - |
| `test_failed_attempts_use_the_same_delay` | réussi | 0.300 s | - |
| `test_lock_after_six_failures_success_resets_and_service_unlocks` | réussi | 1.075 s | - |
| `test_unknown_user_does_not_create_persistent_failure_state` | réussi | 1.425 s | - |
| `test_forced_login_requests_lock_the_known_account` | réussi | 0.592 s | - |
| `test_simultaneous_failed_attempts_are_counted_atomically` | réussi | 0.203 s | - |
| `test_group_access_respects_active_association` | réussi | 0.170 s | - |
| `test_group_access_follows_role_hierarchy[user_groups0-ADMIN-200]` | réussi | 0.017 s | - |
| `test_group_access_follows_role_hierarchy[user_groups1-EDITOR-200]` | réussi | 0.016 s | - |
| `test_group_access_follows_role_hierarchy[user_groups2-VIEWER-200]` | réussi | 0.016 s | - |
| `test_group_access_follows_role_hierarchy[user_groups3-ADMIN-403]` | réussi | 0.017 s | - |
| `test_group_access_follows_role_hierarchy[user_groups4-VIEWER-200]` | réussi | 0.016 s | - |
| `test_group_access_follows_role_hierarchy[user_groups5-EDITOR-403]` | réussi | 0.016 s | - |
| `test_none_mode_virtual_admin_inherits_all_roles` | réussi | 0.017 s | - |
| `test_user_crud_and_collisions_leave_session_usable` | réussi | 0.230 s | - |
| `test_username_and_email_collisions_roll_back[username-duplique]` | réussi | 0.220 s | - |
| `test_username_and_email_collisions_roll_back[email-duplique]` | réussi | 0.221 s | - |
| `test_failed_user_update_rolls_back_all_field_changes` | réussi | 0.152 s | - |
| `test_concurrent_external_provisioning_is_idempotent` | réussi | 0.033 s | - |
| `test_admin_bootstrap_is_idempotent` | réussi | 0.086 s | - |
| `test_admin_bootstrap_does_not_restore_removed_admin_group` | réussi | 0.091 s | - |
| `test_admin_bootstrap_requires_password_only_when_creating_account` | réussi | 0.011 s | - |
| `test_concurrent_admin_bootstrap_is_idempotent` | réussi | 0.108 s | - |
| `test_password_change_and_disable_revoke_all_sessions` | réussi | 0.155 s | - |
| `test_expired_session_is_rejected_and_deleted` | réussi | 0.081 s | - |
| `test_password_is_absent_from_success_and_failure_logs` | réussi | 0.231 s | - |
| `test_external_mode_callback_creates_session_and_maps_allowed_groups` | réussi | 0.030 s | - |
| `test_external_callback_rejects_disabled_user_without_creating_session` | réussi | 0.027 s | - |
| `test_user_provenance_is_persisted_and_external_identity_cannot_be_renamed` | réussi | 0.089 s | - |
| `test_changing_auth_mode_purges_all_persisted_authentication_state` | réussi | 0.173 s | - |
| `test_legacy_external_identity_is_completed_on_matching_callback` | réussi | 0.019 s | - |
| `test_external_login_route_starts_redirect` | réussi | 0.016 s | - |
| `test_oidc_callback_rejects_expected_authentication_errors[state-invalide]` | réussi | 0.017 s | - |
| `test_oidc_callback_rejects_expected_authentication_errors[profil-invalide]` | réussi | 0.017 s | - |
| `test_oidc_callback_rejects_expected_authentication_errors[claim-absent]` | réussi | 0.017 s | - |
| `test_oidc_bad_signature_is_not_accepted` | réussi | 0.018 s | - |
| `test_oidc_network_errors_are_unavailable_and_do_not_leak_details[connection-error]` | réussi | 0.018 s | - |
| `test_oidc_network_errors_are_unavailable_and_do_not_leak_details[timeout]` | réussi | 0.019 s | - |
| `test_auth_errors_are_json_and_auth_responses_are_not_cached` | réussi | 0.018 s | - |
| `test_oidc_missing_subject_creates_no_user_or_session` | réussi | 0.007 s | - |
| `test_internal_logout_requires_csrf_and_revokes_session` | réussi | 0.167 s | - |

#### `tests.test_front` - Français

| Test | Résultat | Durée | Détails |
| --- | --- | ---: | --- |
| `test_privileged_markup_is_absent[False-VIEWER-forbidden0]` | réussi | 0.317 s | - |
| `test_privileged_markup_is_absent[False-EDITOR-forbidden1]` | réussi | 0.310 s | - |
| `test_privileged_markup_is_absent[True-VIEWER-forbidden0]` | réussi | 0.306 s | - |
| `test_privileged_markup_is_absent[True-EDITOR-forbidden1]` | réussi | 0.303 s | - |
| `test_viewer_cannot_call_privileged_routes[/builder]` | réussi | 0.290 s | - |
| `test_viewer_cannot_call_privileged_routes[/builder/search]` | réussi | 0.290 s | - |
| `test_viewer_cannot_call_privileged_routes[/sources]` | réussi | 0.291 s | - |
| `test_viewer_cannot_call_privileged_routes[/administration]` | réussi | 0.297 s | - |
| `test_preferences_are_persisted_and_scoped` | réussi | 0.317 s | - |
| `test_preview_does_not_save_and_versions_are_immutable` | réussi | 0.320 s | - |
| `test_builder_exposes_preview_and_create_actions` | réussi | 0.302 s | - |
| `test_viewer_exports_versions[yaml-code:]` | réussi | 0.301 s | - |
| `test_viewer_exports_versions[geojson-{]` | réussi | 0.300 s | - |
| `test_viewer_exports_versions[gpkg-SQLite format 3]` | réussi | 0.306 s | - |
| `test_viewer_exports_versions[shp-PK]` | réussi | 0.305 s | - |
| `test_viewer_exports_versions[postgis-BEGIN;]` | réussi | 0.298 s | - |
| `test_admin_can_delete_a_version_after_snapshot` | réussi | 0.351 s | - |
| `test_catalog_snapshot_delete_and_restore_are_faithful_and_atomic` | réussi | 0.355 s | - |
| `test_sources_require_confirmation_and_preserve_dependencies` | réussi | 0.313 s | - |
| `test_toml_preview_only_adds_after_validation` | réussi | 0.314 s | - |
| `test_yaml_roundtrip_and_invalid_input` | réussi | 0.330 s | - |
| `test_mutations_require_csrf` | réussi | 0.290 s | - |
| `test_invalid_toml_is_rejected_without_changes[{}]` | réussi | 0.310 s | - |
| `test_invalid_toml_is_rejected_without_changes[source_path=12\ndata_family="incorrect"]` | réussi | 0.296 s | - |
| `test_invalid_toml_is_rejected_without_changes[source_path="https://naturalearth.s3.amazonaws.com"\n[data_family]\ncultural="incorrect"]` | réussi | 0.294 s | - |
| `test_preferences_follow_authentication_context` | réussi | 0.297 s | - |
