# 用户组功能设计

## 1. 数据表设计

### 1.1. 用户组表 (`user_groups`)

用于存储用户组的基本信息。

| 字段名 | 类型 | 描述 |
| --- | --- | --- |
| `id` | Integer | 主键 |
| `name` | String | 组名称，必填 |
| `description` | Text | 组描述，可选 |
| `credits` | Integer | 组的共享积分 |
| `owner_id` | Integer | 组的创建者/所有者，外键关联 `users.id` |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 更新时间 |

### 1.2. 用户与用户组关系表 (`user_group_memberships`)

用于存储用户和用户组之间的多对多关系。

| 字段名 | 类型 | 描述 |
| --- | --- | --- |
| `id` | Integer | 主键 |
| `user_id` | Integer | 用户ID，外键关联 `users.id` |
| `group_id` | Integer | 用户组ID，外键关联 `user_groups.id` |
| `permission_level` | Integer | 组内权限级别，越高权限越大（如：1=普通成员，2=管理员，3=群主），默认为1 |
| `credit_share_limit` | Integer | 用户可共享给该组的积分上限，默认为0 |
| `created_at` | DateTime | 创建时间 |

### 1.3. 项目级别组积分共享授权表 (`project_group_credit_allocations`) - 新增

用于配置用户组的积分在特定项目中的使用权限和额度。

| 字段名 | 类型 | 描述 |
| --- | --- | --- |
| `id` | Integer | 主键 |
| `project_id` | Integer | 项目ID，外键关联 `projects.id` |
| `group_id` | Integer | 提供积分的用户组ID，外键关联 `user_groups.id` |
| `user_id` | Integer | 被授权使用这些积分的用户ID，外键关联 `users.id` |
| `credit_limit` | Integer | 该项目下该用户最多可使用的组积分额度。默认10000。-1或未设置代表无上限 |
| `used_credits` | Integer | 已经使用的额度，默认为0 |
| `granted_by` | Integer | 授权人的用户ID（必须是组内 permission_level > 1 的成员） |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 更新时间 |

### 1.4. 用户表 (`users`) - 变更

需要在用户表中增加一个字段，用于标识用户当前选择的用户组。

| 字段名 | 类型 | 描述 |
| --- | --- | --- |
| `current_group_id` | Integer | 用户当前激活的用户组ID，外键关联 `user_groups.id`，可为空 |

## 2. 基础模块与API接口设计

### 2.1. Pydantic Schemas (数据模型)

- `UserGroupBase`: 用户组基础模型，包含 `name`, `description`。
- `UserGroupCreate`: 创建用户组时使用的模型。
- `UserGroupUpdate`: 更新用户组时使用的模型。
- `UserGroupInDB`: 数据库中存储的用户组模型。
- `UserGroup`: 返回给客户端的用户组模型。
- `UserGroupMembershipBase`: 关系表基础模型。
- `UserGroupMembershipCreate`: 创建关系时使用的模型。
- `UserGroupMembership`: 返回关系信息时使用的模型。
- `UserUpdate`: 更新用户模型时，需要能更新 `current_group_id`。

### 2.2. API Endpoints (接口)

#### 2.2.1. 用户组管理 (`/api/v1/groups`)

- **`POST /`**: 创建一个新的用户组。
    - 需要用户认证。
    - 创建者自动成为该组的 `owner`。
- **`GET /`**: 获取当前用户所属的所有用户组列表。
- **`GET /{group_id}`**: 获取指定用户组的详细信息，包括成员列表。
- **`PUT /{group_id}`**: 更新用户组信息（仅限组所有者或管理员）。
- **`DELETE /{group_id}`**: 删除一个用户组（仅限组所有者）。

#### 2.2.2. 用户组成员管理 (`/api/v1/groups/{group_id}/members`)

- **`POST /`**: 邀请/添加一个新成员到用户组。
    - 可由组所有者或管理员操作。
- **`DELETE /{user_id}`**: 从用户组中移除一个成员。
    - 可由组所有者或管理员操作。
- **`PUT /{user_id}`**: 更新成员在组内的信息，如 `credit_share_limit`。

#### 2.2.3. 用户设置

- **`PUT /api/v1/users/me`**: 更新当前用户信息。
    - 在请求体中可以包含 `current_group_id` 来切换当前用户的激活用户组。
- **`GET /api/v1/users/me/groups`**: 在用户设置的“用户组管理”Tab加载数据，展示我所在的组、组权限和组成员列表。

#### 2.2.4. 项目级积分共享管理 (`/api/v1/projects/{project_id}/group-credits`)
- **`POST /`**: 新增或更新一位用户在该项目的组积分消费上限。仅限对应 Group 内 `permission_level > 1` 的成员操作。
- **`GET /`**: 查询该项目由于该组派发的各种授权使用记录。

## 3. 核心业务逻辑

- **权限与用户组管理**:
    - **前端用户设置Tab**: 增加专门的管理页面（Tab）。可以通过此页面创建新组（自动成为 permission_level=3 的所有者）。
    - 组所有者及管理员（`permission_level > 1`）可以查看并编辑其他成员的权限与积分限制，或将成员踢出。
    - 普通成员只能选择“当前激活的组”及调整自己对组的分享上限。

- **积分使用与扣费变更 (全局共享 vs 项目授权)**:
    - 用户组积分的分配支持“无限制(本组通用)”以及“项目级别控制”。
    - 当用户进行项目外消费（例如基础聊天等），根据组自身的规定扣费。
    - 当用户进行特定项目内消费（如剧本生成，图片生成）时：需要首先查询 `project_group_credit_allocations` 表中，是否有当前组 (`current_group_id`) 给该用户分配的、针对于该项目的积分上限：
        - 如果没有，且组设置必须要求项目授权，就拒绝或者只走该用户个人积分。
        - 如果有，则从该授权记录可用余额(`credit_limit - used_credits`)和组剩余积分同时扣除，并更新 `used_credits`。若 `credit_limit = -1` 则表示无上限。
        - 若组积分不足，则由用户的个人积分补充支付。
    - 无论哪种，都要在 `transaction_history` 里清晰记录。

- **积分贡献 (从个人到组)**:
    - 用户可以将自己的个人积分贡献给当前激活的用户组。
    - 单次或累计贡献的积分额度受到 `user_group_memberships.credit_share_limit` 字段的限制。如果 `credit_share_limit` 为0或未设置，则表示该用户不能向此组贡献积分。
    - 此操作需要一个专门的API接口来处理。

- **信息接收**:
    - 为用户组设计的特定信息（如通知、消息）可以推送给组内所有成员。
- **权限控制**:
    - 需要定义清晰的权限逻辑，例如：谁可以修改组信息，谁可以邀请/移除成员等。


这样的设计涵盖了数据结构、API接口和核心业务逻辑，为接下来的具体代码实现提供了清晰的蓝图。
