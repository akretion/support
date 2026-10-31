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

1. **La version est la clé.** Rejouer un appel avec la même version complète la release
   (union des tickets) sans la dupliquer : une migration rejouée ne crée rien en double.
2. **`next`** est la valeur de version quand aucun numéro n'existe : une seule par
   client, absorbée par la première version numérotée.
3. **Aucune logique GitLab côté serveur** : les ids de tickets arrivent dans le payload.
4. **Une release n'appartient pas à un projet** : elle appartient au client
   (`cross.connect.client`) et peut contenir des tickets de plusieurs projets ;
   `partner_id` est celui du projet des tickets liés.
5. **Une migration ne doit jamais casser un déploiement** : elle tourne aussi sur les
   bases de test, et aucun appel réseau ne s'y fait.
6. **Le déplacement d'étape ne régresse jamais un ticket** (comparaison de séquence) et
   ne casse jamais la réception (try/except par ticket).
7. **Une seule registration par version, avant le déploiement.** `is_sent` n'est jamais
   invalidé : une version déjà envoyée n'est pas renvoyée, même si une migration
   ultérieure y ajoutait des tickets.
8. **Pas de backport** : cible 18.0, pilote sur un projet 18.0.

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
                                                      |     (paramétrées, jamais en arrière)  |
                                                      +---------------------------------------+
```

| Moment                     | Appel de la migration                       | Côté client                                                       | Côté central                                                             |
| -------------------------- | ------------------------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------ |
| merge, déploiement préprod | `version="next"`, `tickets=[...]`           | release `next` créée ou complétée                                 | `next` reçue, tickets liés, étape préprod                                |
| bump, déploiement préprod  | `version="14.0.2610.26.0"`, `tickets=[...]` | release `<V>` créée, tickets de `next` absorbés, `next` supprimée | `<V>` reçue, tickets liés, étape préprod, `next` absorbée puis supprimée |
| déploiement prod           | même appel que la préprod                   | même release, renvoyée                                            | `<V>` reçue, tickets à l'étape prod, `prod_deployed_at` posé             |

Trois règles :

- une release qui a déjà un `prod_deployed_at` ignore tout payload venant de la
  **préprod** ;
- la cron n'envoie **qu'une release par tick** (`is_sent = False`, la plus ancienne par
  `create_date`) ;
- un envoi en échec laisse `is_sent` à faux : la release reste en tête de file et sera
  réessayée.

---

## 5. Décisions

| #   | Décision                                                                                                                                                                                                                               | Raison                                                                                                                                                                       |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Deux modules dans akretion/support : `support_release` (client) et `support_server_release` (serveur), avec des modèles aux noms distincts (`support.release` / `support.server.release`).                                             | Réponse utilisateur ; aucun risque de fusion de modèle.                                                                                                                      |
| D2  | L'information entre par une migration générée qui appelle `env["support.release"]._register_deployment(version=..., tickets=[...])`, sous `if "support.release" not in env`.                                                           | Seul mécanisme disponible au moment de la mise à jour, sans git ni réseau ; la garde évite de casser une base où le module manque.                                           |
| D3  | La version est la clé d'idempotence, `next` quand il n'y a pas de numéro ; la première version numérotée absorbe `next` puis la supprime (le serveur fait de même).                                                                    | Réponse utilisateur ; rejouable, et aucun ticket perdu ou compté deux fois.                                                                                                  |
| D4  | Environnement = `tools.config.get("running_env")`, sans paramètre de module ; seuls `preprod` et `prod` déclenchent un envoi.                                                                                                          | Réponse utilisateur ; `server_environment` fournit déjà la valeur.                                                                                                           |
| D5  | Envoi par cron (10 min) et bouton, une release par tick, la plus ancienne non envoyée ; `is_sent` posé seulement en cas de succès, jamais invalidé.                                                                                    | Réponse utilisateur ; aucun état d'erreur à maintenir.                                                                                                                       |
| D6  | Transport par `cross.connect.server._request()` sur `/cross_connect/release`, route ajoutée à l'endpoint `api-support` existant.                                                                                                       | Infrastructure en place : ni authentification ni endpoint nouveau.                                                                                                           |
| D7  | Le serveur ne dépend ni de GitLab ni de `project_customer_access` : manifeste `cross_connect_server` + `project`.                                                                                                                      | Réponse utilisateur ; le partenaire venant des projets des tickets, plus rien n'a besoin du lien client → projets, et `gitlab_integration` sort de la chaîne de dépendances. |
| D8  | La release n'a pas de `project_id` ; elle porte le `cross_connect_client_id` (issu de la clé d'API) et le `partner_id` **déduit du projet des tickets liés** ; les tickets dont le projet pointe un autre partenaire ne sont pas liés. | Réponse utilisateur : le partenaire vient du projet de la task, pas de la configuration du client.                                                                           |
| D9  | Deux étapes globales paramétrables (préprod, prod) dans les Réglages, appliquées à chaque réception, jamais en arrière, avec rattachement de l'étape au projet si besoin.                                                              | Réponse utilisateur, plus le piège du calcul de `stage_id`.                                                                                                                  |
| D10 | Préprod ignorée pour une version déjà en prod.                                                                                                                                                                                         | Réponse utilisateur.                                                                                                                                                         |
| D11 | Les horodatages de déploiement sont posés par le central à la réception et écrasés à chaque réception.                                                                                                                                 | Le client n'envoie pas de dates, l'heure du central est la seule fiable.                                                                                                     |
| D12 | Versions non validées en format ; `next` normalisé en minuscules.                                                                                                                                                                      | Les versions en usage ont cinq segments.                                                                                                                                     |
| D13 | Pas de backport.                                                                                                                                                                                                                       | Réponse utilisateur.                                                                                                                                                         |

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

- `version` vide → avertissement dans les logs, rien n'est créé, aucune exception ;
- `tickets` absents ou vides → liste vide acceptée ;
- si la release existe déjà, ses tickets sont complétés (union dédoublonnée) ;
- si `version` est numérotée et qu'une `next` existe, ses tickets sont absorbés puis la
  `next` est supprimée, dans la même transaction.

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
invalide. Aucune autre information n'est retournée : les diagnostics (tickets inconnus,
tickets d'un autre partenaire, étapes déplacées ou ignorées) vont dans les logs du
central.

---

## 8. Module `support_release` (client)

Dépend de `support`. Un modèle, une cron, une vue liste, une vue formulaire, un bouton.

### `support.release` (`_rec_name = "version"`)

| Champ     | Type                         | Rôle                                                            |
| --------- | ---------------------------- | --------------------------------------------------------------- |
| `version` | Char, requis, unique, indexé | clé ; `next` pour la future version                             |
| `tickets` | Char                         | JSON de la liste d'ids, dédoublonnée et triée                   |
| `is_sent` | Booléen                      | vrai après un envoi accepté par le central, jamais remis à faux |

`create_date`, posé par Odoo, donne l'ordre d'envoi.

### Méthodes

- `_register_deployment(version, tickets)` : normalise la version, normalise et
  dédoublonne les tickets, crée ou complète la release, absorbe `next` si la version est
  numérotée (§6).
- `_get_environment()` : `tools.config.get("running_env")` si la valeur est `preprod` ou
  `prod`, sinon `False`.
- `_next_release_to_send()` :
  `search([("is_sent", "=", False)], order="create_date, id", limit=1)`.
- `_push_release(release)` :
  `ref("support.support_server")._request("POST", "/release", data=payload)` en
  `sudo()`, puis `is_sent = True`. Toute exception est journalisée et laisse `is_sent` à
  faux.
- `_cron_push_releases()` : sort si `_get_environment()` est faux ; sinon pousse
  `_next_release_to_send()`, dans un try/except (la cron ne lève jamais).
- `_push_pending()` : bouton, boucle sur `_next_release_to_send()` jusqu'à épuisement
  (garde-fou à 100).

### Vues

Réglages > Technique > Releases (`base.group_system`) : liste (version, envoyée) avec
filtre "À envoyer" et bouton "Pousser maintenant", formulaire (tickets en lecture,
bouton d'envoi).

### Tests

- première registration : release créée, `is_sent` faux, tickets corrects ;
- seconde registration de la même version : union, une seule release, `is_sent` inchangé
  ;
- version numérotée avec une `next` existante : absorption puis suppression de `next` ;
- nouveau merge après absorption : une nouvelle `next` est créée ;
- `version="Next"` : normalisé, même release ;
- version vide : avertissement, rien de créé ;
- `running_env` à `dev` : aucun appel ; à `preprod` : un seul appel, sur la plus
  ancienne non envoyée ;
- envoi en échec : `is_sent` reste faux et la release est retentée ;
- clic sur le bouton : toute la file part, une requête par release.

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

`_process(client, payload)` :

1. release existante = `search` sur (`cross_connect_client_id`, `version`) ; si
   `environment == "preprod"` et qu'elle a déjà un `prod_deployed_at`, on s'arrête là
   (log) ;
2. `env["project.task"].browse(ticket_ids).exists()` ; les ids inexistants sont
   journalisés et ignorés ;
3. `partner_id` = premier `partner_id` non vide des projets de ces tickets ; si un
   partenaire est trouvé, les tickets dont le projet pointe un autre partenaire sont
   journalisés et ne sont pas liés ; si aucun projet n'a de partenaire, tous les tickets
   sont liés et la release reste sans partenaire ;
4. upsert : `task_ids` complétés, horodatage de l'environnement posé à `now()` (écrasé)
   ;
5. étapes, voir ci-dessous ;
6. si la version n'est pas `next` et qu'une `next` existe pour ce client : ses tickets
   sont ajoutés à la version, puis la `next` est supprimée.

### Étapes

`_apply_stages(release, environment)` :

- cible = `support_server_release.stage_preprod_id` ou `.stage_prod_id` ;
- pour chaque ticket, on n'écrit que si `(sequence, id)` de la cible est strictement
  au-delà de l'étape courante ;
- si la cible n'est pas dans `task.project_id.type_ids`, elle y est rattachée
  (`_set_stage_on_project_from_task`) pour que la colonne existe dans le kanban ;
- écriture en `sudo()`, une entrée de chatter par ticket (`stage_id` est
  `tracking=True`) ;
- chaque ticket dans son propre try/except, les erreurs sont journalisées.

### Paramétrage

Réglages > Support, bloc "Releases", deux `Many2one('project.task.type')` persistés en
`ir.config_parameter` (`support_server_release.stage_preprod_id`, `.stage_prod_id`).

### Vues

Support > Releases : liste (version, client, partenaire, préprod, prod) avec filtre
"Next", formulaire (tickets en tags). Recherche par client, partenaire, version.

### Sécurité

`ir.model.access.csv` : lecture/écriture pour `base.group_user`. Rien pour les
utilisateurs clients du support : `cross_connect_client_id` et `partner_id` sont là pour
poser plus tard une règle d'accès.

### Tests

- payload `next` en préprod : release créée, tickets liés, étape préprod appliquée,
  `preprod_deployed_at` posé ;
- payload d'une version numérotée alors qu'une `next` existe : tickets absorbés, `next`
  supprimée ;
- payload `prod` : tickets à l'étape prod, `prod_deployed_at` posé ;
- payload préprod sur une version déjà en prod : rien de modifié ;
- cible en amont de l'étape courante : ticket non déplacé ;
- étape non configurée : aucun déplacement, aucune erreur ;
- étape absente de `project.type_ids` : rattachée puis appliquée ;
- `partner_id` de la release = celui du projet du ticket ; un ticket d'un projet d'un
  autre partenaire n'est pas lié ;
- ticket inexistant : ignoré, la release est créée quand même ;
- second envoi identique : rien ne change ;
- `api-key` inconnue → 401 ; `environment` inconnu → 422.

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

| Risque                                                                           | Impact                                                                                                           | Traitement                                                                                                                      |
| -------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Une release en échec reste en tête de file et bloque les suivantes.              | Retard d'envoi.                                                                                                  | Assumé : `is_sent` non posé, erreur journalisée à chaque tick ; on corrige la cause, ou on marque la release envoyée à la main. |
| Environnements de review en `RUNNING_ENV=preprod`.                               | Aucune pollution : la migration n'existe que sur la branche principale, donc ils n'ont aucune release à envoyer. | Rien à faire.                                                                                                                   |
| Tickets de projets rattachés à des partenaires différents dans une même release. | Les minoritaires ne sont pas liés.                                                                               | Partenaire = celui du premier projet rencontré, les autres tickets sont journalisés ; cas anormal par construction.             |
| Migration générée sur une base où le module client n'est pas installé.           | Échec de mise à jour.                                                                                            | Garde `if "support.release" not in env`.                                                                                        |
| Versions en `next` pendant longtemps.                                            | La release `next` grossit.                                                                                       | Comportement voulu.                                                                                                             |
| Étape configurée absente de `project.type_ids`, ou séquences mal ordonnées.      | Ticket non déplacé ou invisible.                                                                                 | Rattachement automatique, logs par ticket ; à vérifier une fois en pilote.                                                      |
| Tickets non résolus non conservés.                                               | Pas de post-mortem en base.                                                                                      | Logs du central uniquement, assumé.                                                                                             |

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
