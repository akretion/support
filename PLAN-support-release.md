# Plan, système de release lié aux tickets

Statut : plan validé, aucun code écrit, en attente du feu vert pour l'exécution. Version
8 du 2026-10-31.

Cadrage :

- la **version est la clé** de la release, `version="next"` quand aucun numéro n'est
  défini ;
- l'appel depuis la migration ne transporte que `version` et `tickets` ;
- le client envoie **une release par tick**, la plus ancienne non envoyée, et ne garde
  qu'un booléen `is_sent` ;
- l'environnement se lit dans **`running_env`** (`server_environment`), sans paramètre
  dédié ;
- côté serveur, **aucune logique GitLab**, une release **sans projet** (client +
  partenaire, tickets multi-projets), et deux **étapes paramétrables** appliquées à la
  réception ;
- modèles réduits au strict nécessaire, noms différents de chaque côté :
  `support.release` (client) et `support.server.release` (serveur) ;
- pas de backport, pilote sur un projet 18.0.

Le script qui produit l'information de release (détection du bump, génération à la volée
d'une migration dans `custom_all`, choix de `next` ou de la version numérotée) est
**hors périmètre** : ce plan ne définit que l'interface par laquelle il alimente les
modules, et la logique des modules.

---

## 1. Objectif

Savoir, dans notre ERP central (erp-fr), quelle version de code d'un projet client est
déployée où, et quels tickets cette version embarque, et faire avancer ces tickets dans
le workflow au fur et à mesure des déploiements.

Deux modules :

- `support_release` (base du client) : enregistre les releases déposées par une
  migration générée dans `custom_all` et les pousse une par une vers le central ;
- `support_server_release` (erp-fr) : reçoit ce push, crée la release, lie les
  `project.task` et applique l'étape correspondant à l'environnement déployé.

---

## 2. Faits vérifiés

| Fait                                                                                                                                                                                                                                                          | Preuve                                                                                                                                                                                 |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Les projets migrent par version de module, convention `@openupgrade.migrate(use_env=True)` et `def migrate(env, version)`. `bin/bump` déplace `migrations/0.0.0/` vers la version et bumpe le manifeste.                                                      | `abilis/odoo/local-src/custom_all/migrations/14.0.2304.18.0/post-configure_product.py` ; `abilis/bump:26-46`                                                                           |
| `"model.name" in env` teste la présence d'un modèle : une migration peut ne rien faire sur une base où le module n'est pas installé.                                                                                                                          | `odoo/src/odoo/api.py:608-610`                                                                                                                                                         |
| `running_env` vient de `server_environment` (valeur `RUNNING_ENV`, repli `ODOO_STAGE`, sinon `test`) et est lisible par `tools.config.get("running_env")`, comme le font déjà les modules `l10n_fr_*` du dépôt.                                               | `server-env/server_environment/server_env.py:47-65` ; `server-env/server_environment/tests/test_environment_variable.py:14-22` ; `l10n-france/l10n_fr_siret/models/res_partner.py:216` |
| En CI, tous les conteneurs tournent avec `RUNNING_ENV=preprod` (dev `dev`, prod `prod`).                                                                                                                                                                      | `abilis/ci.docker-compose.yml:18` ; `abilis/prod.docker-compose.yml:20` ; `abilis/docker-compose.yml:31`                                                                               |
| Les versions en usage ont cinq segments (`14.0.2610.26.0`) : aucune validation `x.y.z`.                                                                                                                                                                       | `abilis/odoo/local-src/custom_all/__manifest__.py:9`                                                                                                                                   |
| L'endpoint `https://erp-fr.akretion.com/api-support` est un `fastapi.endpoint` `app="cross_connect"` ; l'auth par header `api-key` est résolue en `cross.connect.client`.                                                                                     | `server-auth/cross_connect_server/models/fastapi_endpoint.py:24-105` ; `support/support_akretion/data/cross_connect_server.xml`                                                        |
| Côté client, `cross.connect.server` expose `_request(method, path, data)` : préfixe `/cross_connect/`, header `api-key`, lève sur non-2xx. Le record support est `support.support_server`.                                                                    | `raw.githubusercontent.com/OCA/server-auth/18.0/cross_connect_client/models/cross_connect_server.py` ; `support/support/models/cross_connect_server.py:19`                             |
| `project.project` porte `partner_id` (champ « Customer » du core) et `project.task.project_id` le relie : le partenaire d'une release se déduit des tickets, sans configuration.                                                                              | `project/models/project_project.py:89`                                                                                                                                                 |
| Les étapes sont partageables entre projets (`project.task.type.project_ids`), mais `project.task.stage_id` est calculé stocké et son calcul remplace l'étape si elle n'est pas rattachée au projet ; `_set_stage_on_project_from_task()` sert à la rattacher. | `project/models/project_task_type.py:29-33` ; `project/models/project_task.py:154-157,667-675,1074-1081`                                                                               |
| akretion/support a des branches 16.0, 18.0, 19.0 ; le clone est sur la branche agrégée `merged` avec une modification locale dans `support_server/models/project_task.py`.                                                                                    | `git ls-remote --heads origin` ; `git status -sb`                                                                                                                                      |
| Aucun modèle ni champ "release" n'existe aujourd'hui.                                                                                                                                                                                                         | `grep -ri release` sur `odoo/local-src` et `odoo/external-src/support`                                                                                                                 |

---

## 3. Contraintes

1. **La version est la clé.** Rejouer un appel avec la même version remplace ses tickets
   sans dupliquer la release : chaque déploiement renvoie la liste complète des tickets.
2. **`next`** est la valeur de version quand aucun numéro n'existe : une seule par
   client, supprimée à l'arrivée de la première version numérotée.
3. **Aucune logique GitLab côté serveur** : les ids de tickets arrivent dans le payload.
4. **Une release n'appartient pas à un projet** : elle appartient au client
   (`cross.connect.client`) et peut contenir des tickets de plusieurs projets ;
   `partner_id` est celui du projet des tickets liés.
5. **Une migration ne doit jamais casser un déploiement** : elle tourne aussi sur les
   bases de test, et aucun appel réseau ne s'y fait.
6. **L'étape de l'environnement s'applique sans condition** : le payload décrit l'état
   après déploiement, donc une réception hors ordre corrige la précédente.
7. **Une seule registration par version, avant le déploiement.** `is_sent` n'est jamais
   invalidé : une version déjà envoyée n'est pas renvoyée, même si une migration
   ultérieure y ajoutait des tickets.
8. **Rien n'est ignoré en silence.** Ce qui ne peut pas être appliqué à la réception est
   écrit dans le champ `message` de la release ; un appel mal formé lève.
9. **Pas de backport** : cible 18.0, pilote sur un projet 18.0.

---

## 4. Architecture

```
 pipeline du projet client (script de l'utilisateur, hors périmètre)
   merge ou bump -> génère custom_all/migrations/<version>/post-release.py
                              |
                              | _register_deployment(version="next" | "<V>", tickets=[...])
                              v
 Odoo client (support_release)                        Odoo central (support_server_release)
 +-------------------------------------+              +---------------------------------------+
 | support.release                     |   cron 10'   | POST /cross_connect/release           |
 |   version (clé, dont "next")        |--- api-key ->|  support.server.release               |
 |   tickets, is_sent                  |    1/tick    |    client (clé) + partner (projet)    |
 | push la plus ancienne non envoyée   |              |  -> project.task liés (multi-projets)  |
 +-------------------------------------+              |  -> étape préprod OU étape prod       |
                                                      |     (paramétrées, sans condition)     |
                                                      +---------------------------------------+
```

| Moment                     | Appel de la migration                       | Côté client                           | Côté central                                                 |
| -------------------------- | ------------------------------------------- | ------------------------------------- | ------------------------------------------------------------ |
| merge, déploiement préprod | `version="next"`, `tickets=[...]`           | release `next` créée ou remplacée     | `next` reçue, tickets liés, étape préprod                    |
| bump, déploiement préprod  | `version="14.0.2610.26.0"`, `tickets=[...]` | release `<V>` créée, `next` supprimée | `<V>` reçue, tickets liés, étape préprod, `next` supprimée   |
| déploiement prod           | même appel que la préprod                   | même release, renvoyée                | `<V>` reçue, tickets à l'étape prod, `prod_deployed_at` posé |

Trois règles :

- une release qui a déjà un `prod_deployed_at` ignore tout payload venant de la
  **préprod** ;
- la cron n'envoie **qu'une release par tick** (`is_sent = False`, la plus ancienne par
  `create_date`) ;
- un envoi en échec laisse `is_sent` à faux : la release reste en tête de file et sera
  réessayée.

---

## 5. Décisions

| #   | Décision                                                                                                                                                                                                                                   | Raison                                                                                                                                                                       |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Deux modules dans akretion/support : `support_release` (client) et `support_server_release` (serveur), avec des modèles aux noms distincts (`support.release` / `support.server.release`).                                                 | Réponse utilisateur ; aucun risque de fusion de modèle.                                                                                                                      |
| D2  | L'information entre par une migration générée qui appelle `env["support.release"]._register_deployment(version=..., tickets=[...])`, sous `if "support.release" not in env`.                                                               | Seul mécanisme disponible au moment de la mise à jour, sans git ni réseau ; la garde évite de casser une base où le module manque.                                           |
| D3  | La version est la clé d'idempotence, `next` quand il n'y a pas de numéro ; chaque payload porte la liste complète des tickets, donc la première version numérotée supprime simplement `next` (le serveur fait de même).                    | Réponse utilisateur ; rejouable, aucun ticket compté deux fois, aucune fusion à maintenir.                                                                                   |
| D4  | Environnement = `tools.config.get("running_env")`, sans paramètre de module ; seuls `preprod` et `prod` déclenchent un envoi.                                                                                                              | Réponse utilisateur ; `server_environment` fournit déjà la valeur.                                                                                                           |
| D5  | Envoi par cron (10 min), une release par tick, la plus ancienne non envoyée ; `is_sent` posé seulement en cas de succès, jamais invalidé ; un échec remonte dans la cron au lieu d'être avalé.                                             | Réponse utilisateur ; aucun état d'erreur à maintenir, l'exception reste visible.                                                                                            |
| D6  | Transport par `cross.connect.server._request()` sur `/cross_connect/release`, route ajoutée à l'endpoint `api-support` existant.                                                                                                           | Infrastructure en place : ni authentification ni endpoint nouveau.                                                                                                           |
| D7  | Le serveur ne dépend ni de GitLab ni de `project_customer_access` : manifeste `cross_connect_server` + `project`.                                                                                                                          | Réponse utilisateur ; le partenaire venant des projets des tickets, plus rien n'a besoin du lien client → projets, et `gitlab_integration` sort de la chaîne de dépendances. |
| D8  | La release n'a pas de `project_id` ; elle porte le `cross_connect_client_id` (issu de la clé d'API) et le `partner_id` **déduit du projet des tickets liés** ; les tickets dont le projet pointe un autre partenaire ne sont pas liés.     | Réponse utilisateur : le partenaire vient du projet de la task, pas de la configuration du client.                                                                           |
| D9  | Deux étapes globales paramétrables (préprod, prod) dans les Réglages, appliquées à chaque réception sans comparaison avec l'étape courante, avec rattachement de l'étape au projet si besoin.                                              | Réponse utilisateur (« on applique la release et on met à jour l'état sans condition »), plus le piège du calcul de `stage_id`.                                              |
| D10 | Préprod ignorée pour une version déjà en prod.                                                                                                                                                                                             | Réponse utilisateur.                                                                                                                                                         |
| D11 | Les horodatages de déploiement sont posés par le central à la réception et écrasés à chaque réception.                                                                                                                                     | Le client n'envoie pas de dates, l'heure du central est la seule fiable.                                                                                                     |
| D12 | Versions non validées en format ; `next` normalisé en minuscules.                                                                                                                                                                          | Les versions en usage ont cinq segments.                                                                                                                                     |
| D13 | Pas de backport.                                                                                                                                                                                                                           | Réponse utilisateur.                                                                                                                                                         |
| D14 | Tri des releases du central sur `id desc` : la version est une `Char`, un tri `version desc` placerait `14.0.2610.9.0` avant `14.0.2610.26.0`.                                                                                             | Revue de la PR 84.                                                                                                                                                           |
| D15 | Ce qui ne peut pas être appliqué est écrit dans un champ `message` visible sur la release (tickets inconnus, autre partenaire, aucun partenaire, étape non configurée, aucun destinataire) : aucun avertissement silencieux dans les logs. | Revue de la PR 84 (« jamais de choses silencieuses »).                                                                                                                       |
| D16 | Droits : lecture/écriture pour les internes côté central, lecture/écriture pour `base.group_system` côté client, jamais de création ni de suppression depuis l'interface.                                                                  | Revue de la PR 84 : seul le code crée les releases, et supprimer effacerait la seule trace du déploiement.                                                                   |

---

## 6. Interface d'appel depuis la migration

```python
# custom_all/migrations/<version>/post-release.py (généré, exemple sans bump)
from openupgradelib import openupgrade


@openupgrade.migrate(use_env=True)
def migrate(env, version):
    if "support.release" not in env:
        return
    env["support.release"]._register_deployment(version="next", tickets=[25882, 25890])
```

Avec un bump : `version="14.0.2610.26.0"` et les tickets de la version.

- `version` vide → `ValueError` : une migration générée cassée doit se voir, pas
  disparaître dans un log ;
- `tickets` doit être une liste d'ids entiers, sinon `ValueError`, aucun filtrage
  silencieux ;
- si la release existe déjà, ses tickets sont remplacés par ceux du payload ;
- si `version` est numérotée et qu'une `next` existe, la `next` est supprimée, dans la
  même transaction : ses tickets sont déjà dans le payload de la version.

---

## 7. Contrat HTTP

`POST https://<central>/api-support/cross_connect/release`, header
`api-key: <clé du client>`.

```json
{
  "environment": "preprod",
  "version": "next",
  "tickets": [25901, 25912]
}
```

`environment` est `running_env` tel quel ; `preprod` et `prod` sont acceptés, le reste
est refusé (422). Le client vient de la clé d'API ; le partenaire, lui, n'est pas dans
le payload : il se déduit du projet des tickets liés.

Réponse : `{"ok": true}` (200). 401 si la clé est inconnue, 422 si le payload est
invalide (dont une `version` vide). Aucune autre information n'est retournée : les
diagnostics (tickets inconnus, ticket d'un autre partenaire, étape non configurée) sont
écrits dans le champ `message` de la release sur le central.

---

## 8. Module `support_release` (client)

Dépend de `support`. Un modèle, une cron, une vue liste, une vue formulaire.

### `support.release` (`_rec_name = "version"`)

| Champ     | Type                         | Rôle                                                            |
| --------- | ---------------------------- | --------------------------------------------------------------- |
| `version` | Char, requis, unique, indexé | clé ; `next` pour la future version                             |
| `tickets` | `Json`                       | liste d'ids telle que reçue du dernier déploiement              |
| `is_sent` | Booléen                      | vrai après un envoi accepté par le central, jamais remis à faux |

`create_date`, posé par Odoo, donne l'ordre d'envoi.

### Méthodes

- `_register_deployment(version, tickets)` : `strip()` sur la version, `next` replié en
  minuscules, `ValueError` si la version est vide ou si `tickets` n'est pas une liste
  d'ids entiers ; crée la release ou remplace ses tickets ; supprime `next` quand la
  version est numérotée (§6).
- `_get_environment()` : `tools.config.get("running_env")` si la valeur est `preprod` ou
  `prod`, sinon `False`.
- `_next_release_to_send()` : `search([("is_sent", "=", False)], limit=1)` sur l'ordre
  `create_date, id`.
- `_push()` : `ref("support.support_server")._request("POST", "/release", data=payload)`
  en `sudo()`, puis `is_sent = True`. Une exception laisse `is_sent` à faux et remonte.
- `_cron_push_releases()` : sort si `_get_environment()` est faux ; sinon pousse
  `_next_release_to_send()`, sans try/except : une panne doit apparaître dans le log de
  la cron et la release est retentée au tick suivant.

### Vues

Réglages > Releases (`base.group_system`, donc visible sans mode développeur) : liste
(version, tickets, envoyée, date) avec filtre "À envoyer", formulaire en lecture seule.
Pas de bouton : la cron est le seul chemin d'envoi.

### Tests

- première registration : release créée, `is_sent` faux, tickets corrects ;
- seconde registration de la même version : les tickets sont remplacés, une seule
  release, `is_sent` inchangé ;
- version numérotée avec une `next` existante : `next` supprimée, la version garde ses
  propres tickets ;
- nouveau merge après suppression : une nouvelle `next` est créée ;
- `version="Next"` : replié, même release ;
- version vide ou tickets qui ne sont pas une liste d'ids : `ValueError`, rien de créé ;
- `running_env` à `dev` : aucun appel ; à `preprod` : un seul appel, sur la plus
  ancienne non envoyée ;
- envoi en échec : l'exception remonte, `is_sent` reste faux et la release est retentée.

---

## 9. Module `support_server_release` (central)

Dépend de `cross_connect_server` et `project`. Aucune référence GitLab, et aucune
dépendance à `project_customer_access` : le partenaire se déduit des projets des
tickets.

### `support.server.release` (`_rec_name = "version"`)

| Champ                     | Type                           | Rôle                                    |
| ------------------------- | ------------------------------ | --------------------------------------- |
| `version`                 | Char, requis, indexé           | unique par client                       |
| `cross_connect_client_id` | Many2one, requis, indexé       | client propriétaire                     |
| `partner_id`              | Many2one `res.partner`, indexé | `partner_id` du projet des tickets liés |
| `task_ids`                | Many2many `project.task`       | tickets liés, tous projets confondus    |
| `preprod_deployed_at`     | Datetime                       | dernière réception préprod              |
| `prod_deployed_at`        | Datetime                       | dernière réception prod                 |
| `message`                 | Text, lecture seule            | ce qui n'a pas pu être appliqué (D15)   |

Ordre par défaut : `id desc`, donc la dernière release reçue en tête (D14).

Contrainte SQL : unicité (`cross_connect_client_id`, `version`). `project.task` :
`release_ids` Many2many `support.server.release` (relation
`support_server_release_project_task_rel`) et bouton intelligent.

### Router

`routers/release.py` : `POST /cross_connect/release`, dépendances
`authenticated_cross_connect_client` et `odoo_env`, schéma pydantic à trois champs.
`models/fastapi_endpoint.py` ajoute le router via `_get_fastapi_routers()` quand
`self.app == "cross_connect"`. Le router appelle
`env["support.server.release"].sudo()._process(client, payload)`.

### Traitement

`_process(client, payload)` reste courte (une quinzaine de lignes) et délègue :

1. `_get_release(client, version)` : `search` sur (`cross_connect_client_id`,
   `version`), sinon `create` ;
2. si `environment == "preprod"` et que la release a déjà un `prod_deployed_at`, on
   s'arrête là : rien n'est modifié, pas même le champ `message` ;
3. `_filter_tickets(release, ticket_ids)` : résout les ids (`browse().exists()`), met
   dans `message` les ids inconnus, garde les tickets dont le projet porte le partenaire
   de la release (ou le premier partenaire trouvé si la release n'en a pas encore) et
   met dans `message` ceux d'un autre partenaire ; si aucun projet n'a de partenaire,
   aucun ticket n'est lié et `message` l'indique ;
4. `_release_vals(...)` : horodatage de l'environnement à `now()` (écrasé), `message`,
   `task_ids` liés et `partner_id` ;
5. `_apply_stages(stage)` puis, si aucune étape n'est configurée, une ligne dans
   `message` ;
6. `_remove_next_release()` si la version n'est pas `next` ;
7. `_notify_prod_release()` en production.

### Étapes

`_apply_stages(stage)` :

- cible = `support_server_release.stage_preprod_id` ou `.stage_prod_id` ;
- l'étape est écrite sur **chaque** ticket, sans comparaison avec l'étape courante ;
- si la cible n'est pas dans `task.project_id.type_ids`, elle y est rattachée
  (`Command.link`) pour que la colonne existe dans le kanban et que le calcul de
  `stage_id` ne la remplace pas ;
- écriture en `sudo()`, une entrée de chatter par ticket (`stage_id` est
  `tracking=True`) ;
- aucune gestion d'erreur par ticket : une écriture impossible fait échouer la
  réception, ce qui est visible et rejoué par le client.

### Paramétrage

Réglages > Support, bloc "Releases", deux `Many2one('project.task.type')` persistés en
`ir.config_parameter` (`support_server_release.stage_preprod_id`, `.stage_prod_id`).

### Vues

Support > Releases : liste (version, client, partenaire, préprod, prod) avec filtre
"Next", formulaire (tickets en tags). Recherche par client, partenaire, version.

### Sécurité

`ir.model.access.csv` : lecture/écriture pour `base.group_user`, ni création ni
suppression (D16) : seul le code crée une release, et la supprimer effacerait la seule
trace du déploiement. Rien pour les utilisateurs clients du support :
`cross_connect_client_id` et `partner_id` sont là pour poser plus tard une règle
d'accès.

### Tests

- payload `next` en préprod : release créée, tickets liés, étape préprod appliquée,
  `preprod_deployed_at` posé, `message` vide ;
- payload d'une version numérotée alors qu'une `next` existe : `next` supprimée, la
  version garde les tickets de son payload ;
- payload `prod` : tickets à l'étape prod, `prod_deployed_at` posé ;
- payload préprod sur une version déjà en prod : rien de modifié ;
- cible en amont de l'étape courante : le ticket est quand même déplacé (D9) ;
- étape non configurée : aucun déplacement, une ligne dans `message` ;
- étape absente de `project.type_ids` : rattachée puis appliquée ;
- `partner_id` de la release = celui du projet du ticket ; un ticket d'un projet d'un
  autre partenaire n'est pas lié et reste à son étape, avec une ligne dans `message` ;
- projet sans partenaire : aucun ticket lié, `message` l'indique ;
- ticket inexistant : la release est créée quand même et `message` cite l'id ;
- second envoi identique : rien ne change ;
- mail de production : un `mail.mail` avec les destinataires du client, les titres, les
  liens et le `<details>` ; aucun mail en préprod ; aucun mail sans destinataire, mais
  une ligne dans `message` ;
- `api-key` inconnue → 401 ; `environment` inconnu → 422 ; `version` vide → 422.

---

## 10. Par projet client

1. installer `support_release` dans le `spec.yaml` (série 18.0) ;
2. vérifier que `RUNNING_ENV` vaut `preprod` ou `prod` sur les environnements qui
   doivent remonter ;
3. le `cross.connect.server` de support est déjà configuré par `support_akretion`.

Côté erp-fr : installer `support_server_release`, créer le `cross.connect.client` du
client s'il n'existe pas, configurer les deux étapes. Rien à configurer sur les projets
: le partenaire vient du projet du ticket.

---

## 11. Étapes

| #   | Étape                                                                                                                                                               | C'est fait quand                                                                                                                    |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| 0   | Hygiène du clone : commiter ou mettre de côté la modification locale de `support_server/models/project_task.py`, créer `18.0-support-release` depuis `origin/18.0`. | `git status` propre, `git log` part de `e0dca6d`.                                                                                   |
| 1   | Squelettes des deux modules (manifestes, `readme/`, `pyproject.toml`, description), sans logique.                                                                   | `pre-commit run -a` vert, installation sans erreur sur une base de test.                                                            |
| 2   | `support_release` : modèle, `_register_deployment`, absorption de `next`, sécurité.                                                                                 | Tests de registration verts.                                                                                                        |
| 3   | `support_release` : `running_env`, payload, file d'envoi, push, cron, bouton.                                                                                       | Tests d'envoi verts (mock), silence en `dev`.                                                                                       |
| 4   | `support_server_release` : modèle, partenaire, tickets, absorption de `next`, horodatages, garde préprod.                                                           | Tests de traitement verts.                                                                                                          |
| 5   | `support_server_release` : réglages des étapes et application (séquence, rattachement, try/except).                                                                 | Tests d'étapes verts.                                                                                                               |
| 6   | `support_server_release` : router fastapi, schéma, `_get_fastapi_routers`.                                                                                          | `POST /cross_connect/release` répond 200 en base de test avec une clé valide, 401 sans, 422 avec un environnement inconnu.          |
| 7   | Vues, menus, bouton intelligent, filtres.                                                                                                                           | Un `base.group_user` voit la liste et le formulaire côté central ; un utilisateur client ne les voit pas.                           |
| 8   | Migration de référence jouée dans une vraie migration locale.                                                                                                       | La migration crée `next`, une seconde avec une version numérotée l'absorbe.                                                         |
| 9   | Bout en bout local (base erp-fr de test + base projet de test).                                                                                                     | Un tick crée la release, lie les tickets, applique l'étape préprod ; le tick suivant est muet.                                      |
| 10  | README des deux modules et note d'exploitation.                                                                                                                     | `pre-commit run -a` vert, README corrects.                                                                                          |
| 11  | Pilote réel sur un projet 18.0, avec le script.                                                                                                                     | Un merge apparaît en `next` avec ses tickets à l'étape préprod, le bump absorbe `next`, la prod déplace les tickets à l'étape prod. |

---

## 12. Risques

| Risque                                                                           | Impact                                                                                                           | Traitement                                                                                                                                              |
| -------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Une release en échec reste en tête de file et bloque les suivantes.              | Retard d'envoi.                                                                                                  | Assumé : `is_sent` non posé, l'exception remonte dans le log de la cron à chaque tick ; on corrige la cause, ou on marque la release envoyée à la main. |
| Environnements de review en `RUNNING_ENV=preprod`.                               | Aucune pollution : la migration n'existe que sur la branche principale, donc ils n'ont aucune release à envoyer. | Rien à faire.                                                                                                                                           |
| Tickets de projets rattachés à des partenaires différents dans une même release. | Les minoritaires ne sont pas liés.                                                                               | Partenaire = celui du premier projet rencontré, les autres tickets ne sont pas liés et apparaissent dans `message`.                                     |
| Migration générée sur une base où le module client n'est pas installé.           | Échec de mise à jour.                                                                                            | Garde `if "support.release" not in env`.                                                                                                                |
| Versions en `next` pendant longtemps.                                            | La release `next` grossit.                                                                                       | Comportement voulu.                                                                                                                                     |
| Étape configurée absente de `project.type_ids`.                                  | Ticket non déplacé ou invisible.                                                                                 | Rattachement automatique avant l'écriture ; les séquences ne servent plus à rien puisque l'étape s'applique sans condition.                             |
| Tickets non résolus.                                                             | Pas de post-mortem en base.                                                                                      | Conservés dans le champ `message` de la release, avec les autres anomalies.                                                                             |

---

## 13. Plan B

- `_register_deployment` peut être appelée hors migration (bouton, `odoo shell`) : rien
  n'en dépend.
- `_push_release()` peut être appelée depuis un `odoo shell` si la cron ne suffit pas.
- Les deux étapes peuvent être vidées : le module continue de recevoir releases et
  tickets sans y toucher.

---

## 14. Hors périmètre

Script de génération de release ; toute logique GitLab ; règles d'accès par client ;
multi-dépôts par base ; notes de release publiées ; facturation et temps ;
synchronisation inverse ; backport 16.0.

---

## 15. Ce qui reste à faire

Aucune question de conception ouverte. Deux points opérationnels : nommer le projet
pilote 18.0 (étape 11) et vérifier sur sa base que les deux étapes sont rattachées aux
projets et correctement séquencées.

---

## 16. Vérifications exécutées

Tout ce qui suit a été exécuté sur un banc jetable (`odoo:18.0` + postgres 16,
dépendances Python minimales), pas seulement relu.

**Tests unitaires** : 28 tests, 0 échec (`support_release` 16, `support_server_release`
12), plus `pre-commit run` vert sur les deux modules.

**Étape 8, migration réelle** : un module `bench_release_migration` dépendant de
`support_release` est installé en 18.0.1.0.0, puis mis à jour avec une migration générée
dans `migrations/18.0.2.0.0/post-release.py` :

```
next|[11, 12]|f
```

puis en 18.0.3.0.0 avec `version="18.0.2620.1.0"` :

```
18.0.2620.1.0|[11, 12, 13]|f
```

La ligne `next` a disparu, les tickets des deux migrations sont réunis. Le snippet du
README est donc jouable tel quel, `openupgradelib` compris.

**Étape 9, bout en bout** : deux bases Odoo distinctes (`bench_central`, `bench_client`)
plus une troisième pour la prod (`bench_prod`), le central servant réellement
`/api-support` sur HTTP.

| Envoi                                                       | Effet constaté sur le central                                                                                                                                                   |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| préprod depuis `bench_client` (`next`, tickets 1 et 2)      | release `next` créée, `partner_id` = client du projet, `preprod_deployed_at` posé, les 2 tickets déplacés de `New` à `To release`, 2 tickets liés, `is_sent` à vrai côté client |
| prod depuis `bench_prod` (même version, `RUNNING_ENV=prod`) | `prod_deployed_at` posé, les 2 tickets déplacés à `Closed`                                                                                                                      |
| préprod tardif renvoyé après la prod                        | ignoré : ni horodatage préprod modifié, ni ticket déplacé                                                                                                                       |

Deux points d'exploitation découverts à cette occasion, à retenir pour le pilote :

- un `fastapi.endpoint` créé hors interface (`odoo shell`, données de démo) n'est pas
  routé tant que `_handle_registry_sync()` n'a pas été appelé : les routes vivent dans
  la table `endpoint_route`, pas dans le code. Créer l'endpoint par l'interface (ou
  lancer la synchro) avant le premier envoi.
- la base de prod doit être sa propre base : si elle est restaurée depuis un dump de
  préprod, `is_sent` arrive à vrai et la prod ne pousse rien. C'est le comportement
  voulu (`is_sent` n'est jamais remis à faux), mais il faut le savoir avant un
  rafraîchissement de base.

---

## 17. Notification e-mail de mise en production

Ajout demandé après la première livraison. À la réception d'un payload `prod`, et
seulement après l'absorption de `next` (pour que la liste des tickets soit complète), le
central envoie le template `mail_template_release_in_prod` :

- destinataires : les `user_ids` du `cross.connect.client`, c'est-à-dire les
  utilisateurs portail créés par la connexion croisée, filtrés sur `active` et sur la
  présence d'un `email`, dédoublonnés. Aucun champ ajouté au modèle, aucun nouveau
  réglage : une liste vide signifie aucun envoi, avec une ligne de log ;
- contenu : les titres des tickets, chacun pointant vers
  `/odoo/action-project.action_view_task/<id>` construit depuis `get_base_url()`, et la
  description du ticket repliée dans un `<details>` ;
- envoi : `send_mail(force_send=False)`, donc un `mail.mail` en file, expédié par la
  cron de la file de mails. Une panne SMTP ne fait jamais échouer la réception de la
  release ;
- le template est un vrai `mail.template` éditable dans l'interface : rien du contenu
  n'est en dur dans le code, à part les deux helpers `_get_notification_emails()` et
  `_get_task_url()`.

Pas de layout de notification Odoo : `mail.mail_notification_light` et
`mail_notification_layout` ajoutent un lien _Unfollow_ sans jeton, qui ne veut rien dire
pour un utilisateur portail, et un « Powered by Odoo » inutile chez le client. Le corps
du template est donc envoyé tel quel.

**Vérifié** : 31 tests verts, dont trois sur le mail (envoi en prod avec destinataire,
aucun envoi en préprod, aucun envoi sans utilisateur). Rendu réel contrôlé sur la base
du banc après `-u` : sujet `E2E client: version next in production`, liens absolus
`https://erp-fr.akretion.com/odoo/action-project.action_view_task/2`, `<details>` et
description HTML du ticket préservés, aucun lien `mail/unfollow`.

---

## 18. Revue de la PR 84

Les commentaires de `sebastienbeau` primes sur ceux de `rob-beau` en cas de désaccord ;
les points de `rob-beau` qu'il n'a pas contredits sont appliqués. Le détail :

| Commentaire                                                | Traitement                                                                                                                                                                                           |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `_normalize_version` inutile                               | helper supprimé, `strip()` et repli de `next` en minuscules inline                                                                                                                                   |
| `_normalize_tickets` trop complexe                         | helper supprimé : `ValueError` si ce n'est pas une liste d'ids entiers                                                                                                                               |
| `release.tickets = ticket_ids`                             | plus aucune fusion : le payload remplace les tickets (chaque déploiement envoie la liste complète)                                                                                                   |
| savepoint dans `_register_deployment`                      | non appliqué, conformément à la réponse (« on fait un search avant, pas de risque de parallèle »)                                                                                                    |
| `self.tickets` suffisant                                   | champ passé en `Json`, `_get_ticket_ids()` supprimé                                                                                                                                                  |
| pas de try/except dans la cron                             | supprimé : l'exception remonte dans le log de la cron, la release reste non envoyée et sera retentée                                                                                                 |
| `action_push_pending` à dégager                            | méthode, bouton de la vue et les deux tests supprimés ; la cron est le seul chemin d'envoi                                                                                                           |
| `append` plutôt que `+= [x]`                               | appliqué                                                                                                                                                                                             |
| tri `id desc`                                              | appliqué (D14)                                                                                                                                                                                       |
| pas de warning silencieux (tickets inconnus)               | nouveau champ `message` sur la release                                                                                                                                                               |
| pas de warning silencieux (plusieurs partenaires)          | idem : les tickets écartés y sont listés                                                                                                                                                             |
| savepoint dans `_apply_stages`                             | supprimé                                                                                                                                                                                             |
| pas de « never back »                                      | comparaison de séquence supprimée : l'étape s'applique sans condition (D9, plan mis à jour)                                                                                                          |
| `next` supprimée directement                               | fusion des tickets supprimée, simple `unlink()`                                                                                                                                                      |
| `_process` trop longue                                     | découpée en `_get_release`, `_filter_tickets`, `_release_vals`, `_add_message`, `_apply_stages`, `_remove_next_release` ; une quinzaine de lignes                                                    |
| menu de `support_release` sous `base.menu_custom` (debug)  | déplacé sous Réglages avec `groups="base.group_system"`                                                                                                                                              |
| isolation : tout lié quand le projet n'a pas de partenaire | plus aucun ticket lié sans partenaire, la raison est dans `message`                                                                                                                                  |
| réutiliser `_set_stage_on_project_from_task()`             | non appliqué : ce helper rattache l'étape **courante** du ticket, pas la cible ; le code rattache la cible avec `Command.link`, ce qui est le même geste pour la bonne étape. Un test couvre le cas. |
| `version` vide acceptée par le schéma                      | `Field(min_length=1)` + test 422                                                                                                                                                                     |
| `create`/`unlink` ouverts aux internes                     | `1,1,0,0` côté central et côté client (D16)                                                                                                                                                          |
| test `foreign.stage_id` qui ne peut pas échouer            | ticket étranger créé sur une étape en amont, assertion qu'il n'a pas bougé + présence dans `message`                                                                                                 |
| bloc de réglages en structure 16.0                         | `<setting>` dans un `<block>`, plus de `div.app_settings_block` manuel                                                                                                                               |
| test manquant « étape absente de `project.type_ids` »      | ajouté, avec vérification du rattachement                                                                                                                                                            |

Le fonctionnement a changé sur quatre points, tous reportés dans le plan : les tickets
d'un payload remplacent les précédents (D3), l'étape s'applique sans condition (D9), les
anomalies vont dans `message` au lieu des logs (D15), et le bouton d'envoi disparaît
(D5).

**Vérifié** : 32 tests verts sur le banc (14 client, 14 central, 4 router), dont les
nouveaux cas : remplacement des tickets, `ValueError` sur version vide ou tickets
invalides, étape appliquée en arrière, étape rattachée au projet, `message` rempli pour
un ticket inconnu, un ticket d'un autre partenaire, un projet sans partenaire, une étape
non configurée et l'absence de destinataire, `version` vide en 422.
