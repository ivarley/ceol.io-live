# 012 URLs For Everything

Right now, there's not a direct URL accessible way to access every unique record in the system. We want to have two versions of each, one for regular users and one for admins.

| Entity Type | Regular URL | Exists? | Admin URL | Exists? |
|-------------|-------------|---------|-----------|---------|
| session (page) | `/sessions/{path}` | ✅ | `/admin/sessions/{path}` | ✅ |
| session tunes (tab) | `/sessions/{path}/{session_instance_id}/tunes` | ✅ | `admin/sessions/{path}/tunes` | ✅ |
| session logs (tab) | `/sessions/{path}/{session_instance_id}/logs` | ✅ | `admin/sessions/{path}/logs` | ✅ |
| session people / players (tab) | `/sessions/{path}/{session_instance_id}/people` | ✅ | NA | NA |
| session_instance tunes (tab) | `/sessions/{path}/{session_instance_id}/tunes` | ✅ | `admin/sessions/{path}/tunes` | ✅ |
| session_instance players (tab) | `/sessions/{path}/{session_instance_id}/people` | ✅ | NA | NA |
| tune (page) | `/tunes/{tune_id}` | ❌ | `/admin/tunes/{tune_id}` | ✅ |
| tune_setting (modal) | `/tunes/{tune_id}/settings/{setting_id}` | ❌ | `/admin/tunes/{tune_id}/settings/{setting_id}` | ❌ |
| session_tune (modal) | `/sessions/{path}/tunes/{tune_id}` | ✅ | `/admin/sessions/{path}/tunes/{tune_id}` | ✅ |
| session_tune_alias | `/sessions/{path}` | ✅ | `/admin/sessions/{path}` | ✅ |
| session_instance_tune | `/sessions/{path}/{session_instance_id}` | ✅ | `/admin/sessions/{path}/{session_instance_id}` | ❌ |
| person | `/person/{person_id}` | ❌ | `/admin/people/{person_id}` | ✅ |
| user_account | `/person/{person_id}` | ❌ | `/admin/people/{person_id}` | ✅ |
| person_instrument | `/person/{person_id}` | ❌ | `/admin/people/{person_id}` | ✅ |
| person_tune | N/A (private) | — | `/admin/people/{person_id}#tunes` | ✅ (tab, no anchor) |
| session_person | `/sessions/{path}/people` | ✅ | `/admin/sessions/{path}/players` | ✅ |
| session_instance_person | `/sessions/{path}/{session_instance_id}` | ✅ | `/admin/sessions/{path}/{session_instance_id}` | ❌ |
| login | N/A | — | `/admin/login-history` | ✅ (list only) |

## Missing Pages

* session_instance admin link: /admin/sessions/{path}/logs/{session_instance_id} - brings up the logs tab with the instance detail modal
* tune admin link: /admin/tunes/750