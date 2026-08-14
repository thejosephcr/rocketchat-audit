
# Rocket.Chat User Login Audit

Herramienta de auditoría para identificar usuarios de Rocket.Chat que no han iniciado sesión durante un período determinado.

Tool to audit Rocket.Chat users and identify accounts that have not logged in for a configurable period.

---

## 🇪🇸 Español

### Descripción

Este script consulta la API de Rocket.Chat y genera un archivo CSV con información de los usuarios y su actividad de inicio de sesión.

El objetivo principal es identificar cuentas que:

- No han iniciado sesión durante más de un número configurable de meses.
- Nunca han iniciado sesión.
- Son cuentas recientemente creadas.
- No pueden ser clasificadas porque Rocket.Chat no proporciona su fecha de creación.

El script es **read-only**: no modifica, elimina, desactiva ni realiza ninguna acción sobre las cuentas de Rocket.Chat.

---

### Características

- Compatible con Rocket.Chat API.
- No requiere dependencias externas de Python.
- Utiliza únicamente la librería estándar de Python.
- Obtiene todos los usuarios mediante `users.list`.
- Utiliza `users.info` únicamente cuando `lastLogin` no está disponible.
- Permite configurar el período de inactividad.
- Permite configurar el período considerado como cuenta nueva.
- Genera un archivo CSV.
- Incluye estadísticas al finalizar la ejecución.

---

### Requisitos

- Python 3.
- Acceso a la API de Rocket.Chat.
- Un usuario/API token con permisos suficientes para consultar información de otros usuarios.
- Permiso:

```text
view-full-other-user-info
````

---

### Variables de entorno

El script utiliza las siguientes variables:

| Variable                | Descripción                                 |
| ----------------------- | ------------------------------------------- |
| `ROCKETCHAT_URL`        | URL de la instancia de Rocket.Chat          |
| `ROCKETCHAT_AUTH_TOKEN` | Token de autenticación                      |
| `ROCKETCHAT_USER_ID`    | ID del usuario utilizado para autenticación |

Ejemplo:

```bash
export ROCKETCHAT_URL="https://chat.example.com"
export ROCKETCHAT_AUTH_TOKEN="your-token"
export ROCKETCHAT_USER_ID="your-user-id"
```

También pueden proporcionarse únicamente durante la ejecución:

```bash
ROCKETCHAT_URL="https://chat.example.com" \
ROCKETCHAT_AUTH_TOKEN="your-token" \
ROCKETCHAT_USER_ID="your-user-id" \
python3 rocketchat_audit.py
```

No es necesario guardar las credenciales dentro del código.

---

### Configuración

En el script existen dos variables principales:

```python
INACTIVE_MONTHS = 6
NEW_ACCOUNT_DAYS = 7
```

#### `INACTIVE_MONTHS`

Define cuántos meses deben pasar desde el último login para considerar una cuenta inactiva.

Ejemplo:

```python
INACTIVE_MONTHS = 6
```

Generará la categoría:

```text
INACTIVE_6_MONTHS
```

Si se cambia a:

```python
INACTIVE_MONTHS = 3
```

la categoría será automáticamente:

```text
INACTIVE_3_MONTHS
```

#### `NEW_ACCOUNT_DAYS`

Define cuántos días se consideran como período de gracia para una cuenta nueva.

Por ejemplo:

```python
NEW_ACCOUNT_DAYS = 7
```

Una cuenta creada hace menos de 7 días y que nunca ha iniciado sesión será clasificada como:

```text
NEW_ACCOUNT
```

---

### Lógica de clasificación

El script utiliza la siguiente lógica:

```text
                    Usuario
                       │
                       ▼
                  users.list
                       │
             ┌─────────┴─────────┐
             │                   │
       lastLogin existe    lastLogin = null
             │                   │
             ▼                   ▼
       Calcular fecha        users.info
       de inactividad             │
             │                    ▼
             │              Obtener createdAt
             │                    │
             │             ┌──────┴──────┐
             │             │             │
             │          < 7 días      >= 7 días
             │             │             │
             │             ▼             ▼
             │       NEW_ACCOUNT   NEVER_LOGGED_IN
             │
             ▼
      ┌──────┴──────┐
      │             │
   > 6 meses     <= 6 meses
      │             │
      ▼             ▼
 INACTIVE_6      ACTIVE
 MONTHS
```

---

### Categorías

El CSV puede contener las siguientes categorías:

#### `ACTIVE`

El usuario inició sesión dentro del período configurado.

#### `INACTIVE_6_MONTHS`

El último inicio de sesión ocurrió hace más de `INACTIVE_MONTHS`.

El número se genera dinámicamente.

Ejemplo:

```text
INACTIVE_6_MONTHS
```

o:

```text
INACTIVE_3_MONTHS
```

#### `NEVER_LOGGED_IN`

El usuario nunca ha iniciado sesión y la cuenta tiene al menos `NEW_ACCOUNT_DAYS` días.

#### `NEW_ACCOUNT`

El usuario nunca ha iniciado sesión y la cuenta fue creada hace menos de `NEW_ACCOUNT_DAYS`.

#### `UNKNOWN_NO_CREATED_DATE`

Rocket.Chat no proporcionó `createdAt`, por lo que no es posible determinar si se trata de una cuenta nueva o antigua.

Este estado es especialmente relevante para algunas cuentas creadas mediante SSO/Gmail.

El script **no asume** que estas cuentas sean antiguas o inactivas.

#### `INVALID_LAST_LOGIN`

La API devolvió un valor para `lastLogin`, pero el formato de fecha no pudo ser procesado.

---

### API utilizada

El script utiliza principalmente:

```text
GET /api/v1/users.list
```

para obtener la lista de usuarios.

Cuando un usuario no tiene `lastLogin`, se realiza una consulta adicional:

```text
GET /api/v1/users.info
```

para obtener información adicional, principalmente:

```text
createdAt
lastLogin
```

Esto evita realizar una llamada `users.info` para cada usuario.

Por ejemplo, si existen 500 usuarios pero solamente 20 no tienen `lastLogin:

```text
1 × users.list
20 × users.info
```

en lugar de:

```text
1 × users.list
500 × users.info
```

---

### Archivo generado

El script genera:

```text
rocketchat_users.csv
```

Las columnas son:

| Columna            | Descripción                           |
| ------------------ | ------------------------------------- |
| `username`         | Nombre de usuario                     |
| `name`             | Nombre completo                       |
| `email`            | Dirección de correo                   |
| `createdAt`        | Fecha de creación de la cuenta        |
| `account_age_days` | Antigüedad de la cuenta en días       |
| `lastLogin`        | Último inicio de sesión               |
| `inactive_days`    | Días desde el último login            |
| `category`         | Clasificación de la cuenta            |
| `active`           | Estado activo/inactivo de Rocket.Chat |
| `type`             | Tipo de usuario                       |
| `roles`            | Roles asignados                       |

---

### Ejecución local

Ejemplo:

```bash
ROCKETCHAT_URL="https://chat.example.com" \
ROCKETCHAT_AUTH_TOKEN="your-token" \
ROCKETCHAT_USER_ID="your-user-id" \
python3 rocketchat_audit.py
```

Resultado esperado:

```text
==============================================
 Rocket.Chat User Login Audit
==============================================

Connecting to Rocket.Chat...
Users retrieved: 347

==============================================
 Results
==============================================
Cutoff date:          2026-02-14T...
New accounts:         3
Active:               281
Inactive > 6 months:  42
Never logged in:      18
Unknown created date: 3
Invalid login:        0

users.info requests:  24
users.info errors:    0

CSV generated:        rocketchat_users.csv
==============================================
```

---

### Seguridad

El script es de solo lectura y únicamente realiza solicitudes `GET` a la API de Rocket.Chat.

No realiza:

* Eliminación de usuarios.
* Desactivación de usuarios.
* Modificación de cuentas.
* Cambios de roles.
* Cambios de contraseñas.
* Cambios de configuración.

Las credenciales deben almacenarse mediante variables de entorno o mecanismos seguros de CI/CD.

No se recomienda almacenar tokens directamente en el código fuente.

---

### GitLab CI/CD

El script puede ejecutarse mediante GitLab CI/CD de forma periódica.

Las siguientes variables pueden configurarse como **CI/CD Variables**:

```text
ROCKETCHAT_URL
ROCKETCHAT_AUTH_TOKEN
ROCKETCHAT_USER_ID
```

El token debe configurarse como una variable protegida/oculta según las políticas de seguridad de GitLab de la organización.

El archivo CSV puede almacenarse como artifact del pipeline.

---

## 🇺🇸 English

### Description

This script queries the Rocket.Chat API and generates a CSV report containing user information and login activity.

Its main purpose is to identify accounts that:

* Have not logged in for more than a configurable number of months.
* Have never logged in.
* Are newly created accounts.
* Cannot be classified because Rocket.Chat does not provide their creation date.

The script is **read-only**: it does not modify, delete, deactivate, or otherwise change Rocket.Chat accounts.

---

### Features

* Compatible with the Rocket.Chat API.
* No external Python dependencies.
* Uses only the Python standard library.
* Retrieves users using `users.list`.
* Uses `users.info` only when `lastLogin` is unavailable.
* Configurable inactivity threshold.
* Configurable new-account grace period.
* Generates a CSV report.
* Displays execution statistics.

---

### Requirements

* Python 3.
* Access to the Rocket.Chat API.
* An API user/token with sufficient permissions to retrieve other users' information.
* Permission:

```text
view-full-other-user-info
```

---

### Environment Variables

The script requires:

| Variable                | Description                   |
| ----------------------- | ----------------------------- |
| `ROCKETCHAT_URL`        | Rocket.Chat instance URL      |
| `ROCKETCHAT_AUTH_TOKEN` | Authentication token          |
| `ROCKETCHAT_USER_ID`    | ID of the authentication user |

Example:

```bash
export ROCKETCHAT_URL="https://chat.example.com"
export ROCKETCHAT_AUTH_TOKEN="your-token"
export ROCKETCHAT_USER_ID="your-user-id"
```

The variables can also be supplied only for a single execution:

```bash
ROCKETCHAT_URL="https://chat.example.com" \
ROCKETCHAT_AUTH_TOKEN="your-token" \
ROCKETCHAT_USER_ID="your-user-id" \
python3 rocketchat_audit.py
```

Credentials do not need to be stored in the source code.

---

### Configuration

The script contains two main configuration variables:

```python
INACTIVE_MONTHS = 6
NEW_ACCOUNT_DAYS = 7
```

#### `INACTIVE_MONTHS`

Defines how many months must have passed since the user's last login for the account to be considered inactive.

Example:

```python
INACTIVE_MONTHS = 6
```

The resulting category will be:

```text
INACTIVE_6_MONTHS
```

Changing it to:

```python
INACTIVE_MONTHS = 3
```

will automatically generate:

```text
INACTIVE_3_MONTHS
```

#### `NEW_ACCOUNT_DAYS`

Defines the grace period for newly created accounts.

For example:

```python
NEW_ACCOUNT_DAYS = 7
```

An account created less than 7 days ago with no login will be classified as:

```text
NEW_ACCOUNT
```

---

### Classification Logic

The script follows this logic:

```text
                     User
                       │
                       ▼
                  users.list
                       │
             ┌─────────┴─────────┐
             │                   │
       lastLogin exists    lastLogin = null
             │                   │
             ▼                   ▼
       Calculate login        users.info
       inactivity date             │
             │                    ▼
             │              Get createdAt
             │                    │
             │             ┌──────┴──────┐
             │             │             │
             │          < 7 days      >= 7 days
             │             │             │
             │             ▼             ▼
             │       NEW_ACCOUNT   NEVER_LOGGED_IN
             │
             ▼
      ┌──────┴──────┐
      │             │
   > 6 months     <= 6 months
      │             │
      ▼             ▼
 INACTIVE_6      ACTIVE
 MONTHS
```

---

### Categories

The CSV may contain the following categories:

#### `ACTIVE`

The user logged in within the configured inactivity period.

#### `INACTIVE_6_MONTHS`

The user's last login was more than `INACTIVE_MONTHS` ago.

The number is generated dynamically.

Examples:

```text
INACTIVE_6_MONTHS
```

or:

```text
INACTIVE_3_MONTHS
```

#### `NEVER_LOGGED_IN`

The user has never logged in and the account is older than `NEW_ACCOUNT_DAYS`.

#### `NEW_ACCOUNT`

The user has never logged in and the account was created less than `NEW_ACCOUNT_DAYS` ago.

#### `UNKNOWN_NO_CREATED_DATE`

Rocket.Chat did not provide `createdAt`, so the script cannot determine whether the account is new or old.

This may occur with some SSO/Gmail-created accounts.

The script **does not assume** that these accounts are old or inactive.

#### `INVALID_LAST_LOGIN`

The API returned a `lastLogin` value, but the date format could not be parsed.

---

### API Usage

The script primarily uses:

```text
GET /api/v1/users.list
```

to retrieve the list of users.

When a user does not have `lastLogin`, an additional request is made using:

```text
GET /api/v1/users.info
```

to retrieve additional information, mainly:

```text
createdAt
lastLogin
```

This avoids making an additional `users.info` request for every user.

For example, if there are 500 users and only 20 have no `lastLogin`:

```text
1 × users.list
20 × users.info
```

instead of:

```text
1 × users.list
500 × users.info
```

---

### Generated File

The script generates:

```text
rocketchat_users.csv
```

Columns:

| Column             | Description                        |
| ------------------ | ---------------------------------- |
| `username`         | Username                           |
| `name`             | Full name                          |
| `email`            | Email address                      |
| `createdAt`        | Account creation date              |
| `account_age_days` | Account age in days                |
| `lastLogin`        | Last login timestamp               |
| `inactive_days`    | Days since last login              |
| `category`         | Account classification             |
| `active`           | Rocket.Chat active/inactive status |
| `type`             | User type                          |
| `roles`            | Assigned roles                     |

---

### Local Execution

Example:

```bash
ROCKETCHAT_URL="https://chat.example.com" \
ROCKETCHAT_AUTH_TOKEN="your-token" \
ROCKETCHAT_USER_ID="your-user-id" \
python3 rocketchat_audit.py
```

Expected output:

```text
==============================================
 Rocket.Chat User Login Audit
==============================================

Connecting to Rocket.Chat...
Users retrieved: 347

==============================================
 Results
==============================================
Cutoff date:          2026-02-14T...
New accounts:         3
Active:               281
Inactive > 6 months:  42
Never logged in:      18
Unknown created date: 3
Invalid login:        0

users.info requests:  24
users.info errors:    0

CSV generated:        rocketchat_users.csv
==============================================
```

---

### Security

The script is read-only and only performs `GET` requests against the Rocket.Chat API.

It does not:

* Delete users.
* Disable users.
* Modify accounts.
* Change roles.
* Change passwords.
* Modify Rocket.Chat configuration.

Credentials should be stored using environment variables or secure CI/CD mechanisms.

Do not store API tokens directly in the source code.

---

### GitLab CI/CD

The script can be executed periodically using GitLab CI/CD.

The following variables can be configured as **GitLab CI/CD Variables**:

```text
ROCKETCHAT_URL
ROCKETCHAT_AUTH_TOKEN
ROCKETCHAT_USER_ID
```

The authentication token should be configured as a protected/masked variable according to the organization's GitLab security policies.

The generated CSV can be stored as a pipeline artifact.