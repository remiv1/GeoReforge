"""Pages and HTMX fragments with server-side verified permissions.

.. routes::
    - `/`: Home page.
    - `/signin`: Sign-in page.
    - `/catalogs`: Catalogs page.
    - `/catalogs/<int:identifier>`: Catalog detail page.
    - `/maps`: Maps page.
    - `/maps/<int:identifier>.geojson`: Map GeoJSON data.
    - `/maps/options`: Map options page.
    - `/maps/difference`: Map difference page.
    - `/catalogs/<int:identifier>/export/<format_name>`: Export catalog in specified format.
    - `/builder`: Builder page.
    - `/builder/search`: Builder search page.
    - `/builder/preview`: Builder preview page.
    - `/builder/save`: Builder save endpoint.
    - `/catalogs/import`: Catalog import page.
    - `/profile`: User profile page.
    - `/preferences`: User preferences page.
    - `/sources`: Sources page.
    - `/sources/preview`: Sources preview page.
    - `/sources/apply`: Apply sources endpoint.
    - `/sources/delete-preview`: Delete sources preview endpoint.
    - `/sources/delete`: Delete sources endpoint.
    - `/administration`: Administration page.
    - `/administration/<int:identifier>/unlock`: Unlock administration item endpoint.

.. module_author:: Rémi Verschuur <rverschuur@audit-io.fr>
.. version:: 1.0.0
"""

from __future__ import annotations

from datetime import date
from typing import Any, cast

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from itsdangerous import BadSignature
from requests import RequestException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from werkzeug import Response as WerkzeugResponse
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename
from werkzeug.wrappers import Response as WerkzeugResponse
import yaml

from auth.decorators import ROLE_LEVELS, get_current_user, require_group
from auth.manager import AuthManager
from auth.models import User
from auth.services import UserService
from ..common.db_objects.geo_forged import GeoForged, GeoForgedItem
from ..common.db_objects.geo_zones import GeographicZone
from ..common.db_objects.users import User as DbUser
from .exports import export_zone
from .geometry import OPERATIONS, feature, polygonal, read_geometry
from .services import build_zone, preferences, save_zone
from .sources import apply_sources, prepare_sources

web_bp = Blueprint(
    "web",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/assets",
)
CAPABILITIES = {
    "catalogs:read": "VIEWER",
    "maps:read": "VIEWER",
    "profile:read": "VIEWER",
    "zones:edit": "EDITOR",
    "sources:manage": "ADMIN",
    "users:manage": "ADMIN",
}
_MESSAGE_PAGE = "fragments/message.html"

def _database() -> Session:
    """Get the current database session.

    :return: Database session.
    :rtype: Session
    """
    return current_app.extensions["georeforge_database"].session()


def _user() -> User:
    """Get the current authenticated user.

    :return: Current user.
    :rtype: User
    """
    return cast(User, get_current_user())


def _can(capability: str) -> bool:
    """Check if the current user has the specified capability.

    :param capability: Capability to check.
    :type capability: str
    :return: True if the user has the capability, False otherwise.
    :rtype: bool
    """
    user = get_current_user()
    return user is not None and any(
        ROLE_LEVELS.get(group, -1) >= ROLE_LEVELS[CAPABILITIES[capability]]
        for group in user.groups
    )


def _page(template: str, active: str, **values: Any) -> str:
    """Render a web page with the specified template and context.

    :param template: Template name without the "pages/" prefix and ".html" suffix.
    :type template: str
    :param active: Active page identifier.
    :type active: str
    :param values: Additional context values to pass to the template.
    :type values: Any
    :return: Rendered HTML page.
    :rtype: str
    """
    template = f"pages/{template}.html"
    context: dict[str, Any] = dict(
        active=active,
        user=get_current_user(),
        can=_can,
        today=date.today(),
        operations=OPERATIONS,
        **values
    )
    if context["user"] is not None:
        context["prefs"] = preferences(_database(), _user())
    if request.headers.get("HX-Request") == "true":
        return render_template(template, **context)
    return render_template("base.html", content_template=template, **context)


def _record(identifier: int) -> GeoForged:
    """Retrieve a GeoForged record by its identifier.

    :param identifier: Identifier of the GeoForged record.
    :type identifier: int
    :return: GeoForged record.
    :rtype: GeoForged
    :raises: 404 if the record is not found.
    """
    record = _database().get(GeoForged, identifier)
    if record is None:
        abort(404)
    return record


def _query() -> str:
    """Retrieve the search query from the request arguments.

    :return: Search query string, limited to 100 characters.
    :rtype: str
    """
    return request.args.get("q", "").strip()[:100]


def _source_query() -> Any:
    """Construct a query for GeographicZone sources based on the search term.

    :return: SQLAlchemy query object for GeographicZone sources.
    :rtype: Any
    """
    query = select(GeographicZone).order_by(GeographicZone.name, GeographicZone.id)
    if term := _query():
        query = query.where(
            or_(
                GeographicZone.name.icontains(term, autoescape=True),
                GeographicZone.code.icontains(term, autoescape=True)
            )
        )
    return query


def _definition() -> dict[str, Any]:
    """Retrieve the definition of a GeoForged record from the request form.

    :return: Dictionary containing the definition of the GeoForged record.
    :rtype: dict[str, Any]
    :raises: ValueError if the number of source IDs and operations do not match.
    """
    source_ids = request.form.getlist("source_id")
    operations = request.form.getlist("operation")
    if len(source_ids) != len(operations):
        raise ValueError("Operations and source IDs do not match.")
    return {
        "code": request.form.get("code", ""),
        "name": request.form.get("name", ""),
        "description": request.form.get("description", ""),
        "from_date": request.form.get("from_date", ""),
        "operations": [
            {
                "source_id": source,
                "operation": operation,
            } for source, operation in zip(source_ids, operations)
        ],
    }


@web_bp.after_request
def protect_page_cache(response: Response) -> Response:
    """Prevent caching of custom pages and their fragments.

    :param response: Flask response object.
    :type response: Response
    :return: Modified Flask response object with cache prevention headers.
    :rtype: Response
    """
    if not request.path.startswith("/assets/"):
        response.headers["Cache-Control"] = "no-store"
        response.vary.add("HX-Request")
        response.vary.add("Cookie")
    return response


@web_bp.errorhandler(HTTPException)
def web_error(error: HTTPException) -> tuple[str, int]:
    """Handle web errors and display an error page.

    :param error: HTTP exception object.
    :type error: HTTPException
    :return: Rendered error page and HTTP status code.
    :rtype: tuple[str, int]
    """
    return _page("error", "", error=error.description, status=error.code), error.code or 500


@web_bp.errorhandler(ValueError)
@web_bp.errorhandler(BadSignature)
def invalid_input(error: Exception) -> tuple[str, int]:
    """Display an input error without keeping an open transaction.

    :param error: Exception object representing the input error.
    :type error: Exception
    :return: Rendered error page and HTTP status code.
    :rtype: tuple[str, int]
    """
    _database().rollback()
    message = (
        "Preview has expired or is not valid."
        if isinstance(error, BadSignature)
        else str(error)
    )
    return render_template(
        _MESSAGE_PAGE,
        message=message,
        kind="error",
    ), 422


@web_bp.errorhandler(IntegrityError)
def conflicting_input(_error: IntegrityError) -> tuple[str, int]:
    """Return a conflict error without exposing SQL data.

    :param _error: IntegrityError exception object.
    :type _error: IntegrityError
    :return: Rendered error page and HTTP status code.
    :rtype: tuple[str, int]
    """
    _database().rollback()
    return render_template(
        _MESSAGE_PAGE,
        message="This operation conflicts with existing data.",
        kind="error",
    ), 409


@web_bp.get("/signin")
def signin() -> str | WerkzeugResponse:
    """Display the internal sign-in page or initiate external authentication.

    :return: Rendered sign-in page or redirect response.
    :rtype: str | WerkzeugResponse
    """
    manager: AuthManager = current_app.extensions["auth_manager"]
    if get_current_user() is not None:
        return redirect(url_for("web.catalogs"))
    if manager.mode == "external":
        session["web_login"] = True
        return redirect(url_for("auth.login"))
    return _page("signin", "", mode=manager.mode)


@web_bp.get("/")
def index() -> WerkzeugResponse:
    """Open the interface after authentication and navigation choice.

    :return: Redirect response to the appropriate page based on user authentication and preferences.
    :rtype: WerkzeugResponse
    """
    if get_current_user() is None:
        return redirect(url_for("web.signin"))
    if preferences(_database(), _user()).navigation is None:
        return redirect(url_for("web.profile"))
    return redirect(url_for("web.catalogs"))


@web_bp.get("/catalogs")
@require_group("VIEWER")
def catalogs() -> str:
    """Display catalogs grouped by code and their versions.

    :return: Rendered catalogs page.
    :rtype: str
    """
    latest = select(GeoForged.code, func.max(GeoForged.version).label("version")) \
        .group_by(GeoForged.code).subquery()
    query = select(GeoForged) \
        .join(
            latest,
            (GeoForged.code == latest.c.code) & (GeoForged.version == latest.c.version)
        )
    if term := _query():
        query = query.where(
            or_(
                GeoForged.name.icontains(term, autoescape=True),
                GeoForged.code.icontains(term, autoescape=True),
            )
        )
    page = max(request.args.get("page", 1, type=int), 1)
    records = _database() \
        .scalars(query.order_by(GeoForged.name).offset((page - 1) * 50).limit(51)) \
        .all()
    return _page(
        "catalogs",
        "catalogs",
        records=records[:50],
        has_next=len(records) > 50,
        page=page,
        query=_query(),
    )


@web_bp.get("/catalogs/<int:identifier>")
@require_group("VIEWER")
def catalog_detail(identifier: int) -> str:
    """Display the detail of a zone in the side panel.

    :param identifier: Identifier of the catalog record.
    :type identifier: int
    :return: Rendered detail fragment.
    :rtype: str
    """
    record = _record(identifier)
    versions = _database() \
        .scalars(
            select(GeoForged) \
                .where(GeoForged.code == record.code) \
                .order_by(GeoForged.version.desc())
        ) \
        .all()
    return render_template(
        "fragments/detail.html",
        record=record,
        versions=versions,
        can=_can,
        operations=OPERATIONS,
    )


@web_bp.get("/maps")
@require_group("VIEWER")
def maps() -> str:
    """Display only the constructed zones in the map selection.

    :return: Rendered maps page.
    :rtype: str
    """
    records = _database() \
        .scalars(
            select(GeoForged) \
                .order_by(GeoForged.code, GeoForged.version.desc())
        ) \
        .all()
    selected = request.args.get("zone", type=int)
    return _page("maps", "maps", records=records, selected=selected)


@web_bp.get("/maps/<int:identifier>.geojson")
@require_group("VIEWER")
def map_data(identifier: int) -> Response:
    """Expose the geometry of a constructed version.

    :param identifier: Identifier of the map record.
    :type identifier: int
    :return: GeoJSON representation of the map geometry.
    :rtype: Response
    """
    record = _record(identifier)
    return jsonify(
        feature(
            read_geometry(record.geometry),
            code=record.code,
            name=record.name,
            version=record.version,
        )
    )


@web_bp.get("/maps/options")
@require_group("VIEWER")
def map_options() -> Response:
    """List only the constructed zones for the navigation menu.

    :return: JSON list of constructed zones.
    :rtype: Response
    """
    records = _database() \
        .scalars(
            select(GeoForged)
                .order_by(GeoForged.name, GeoForged.version.desc())
        ) \
        .all()
    return jsonify([{
        "id": record.id,
        "code": record.code,
        "name": record.name,
        "version": record.version,
    } for record in records])


@web_bp.get("/maps/difference")
@require_group("VIEWER")
def difference() -> Response:
    """Return the removed, added, and common areas between two versions.

    :return: JSON object representing the differences between two map versions.
    :rtype: Response
    """
    first = read_geometry(_record(request.args.get("first", 0, type=int)).geometry)
    second = read_geometry(_record(request.args.get("second", 0, type=int)).geometry)
    return jsonify(type="FeatureCollection", features=[
        feature(polygonal(first.difference(second)), change="removed"),
        feature(polygonal(second.difference(first)), change="added"),
        feature(polygonal(first.intersection(second)), change="shared"),
    ])


@web_bp.get("/catalogs/<int:identifier>/export/<format_name>")
@require_group("VIEWER")
def download(identifier: int, format_name: str) -> Response:
    """Download a version in the requested format.

    :param identifier: Identifier of the catalog record.
    :type identifier: int
    :param format_name: Desired export format.
    :type format_name: str
    :return: Response containing the exported file.
    :rtype: Response
    """
    record = _record(identifier)
    content, mime, extension = export_zone(record, format_name)
    response = make_response(content)
    response.content_type = mime
    filename = secure_filename(f"{record.code}-v{record.version}") or f"zone-{identifier}"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}.{extension}"'
    return response


@web_bp.get("/builder")
@require_group("EDITOR")
def builder() -> str:
    """Open the builder or prepare a new version.

    :return: Rendered builder page.
    :rtype: str
    """
    identifier = request.args.get("from", type=int)
    record = _record(identifier) if identifier else None
    return _page("builder", "builder", record=record)


@web_bp.get("/builder/search")
@require_group("EDITOR")
def builder_search() -> str:
    """Search for sources without exposing the admin space.

    :return: Rendered source picker fragment.
    :rtype: str
    """
    records = _database().scalars(_source_query().limit(30)).all()
    return render_template("fragments/source_picker.html", records=records)


@web_bp.post("/builder/preview")
@require_group("EDITOR")
def builder_preview() -> Response:
    """Compute the preview without saving a version.

    :return: JSON representation of the preview geometry.
    :rtype: Response
    """
    _, geometry = build_zone(_database(), _definition())
    return jsonify(feature(geometry))


@web_bp.post("/builder/save")
@require_group("EDITOR")
def builder_save() -> Response:
    """Save a new version after validation.

    :return: Response indicating the result of the save operation.
    :rtype: Response
    """
    record = save_zone(_database(), _definition(), _user())
    response = make_response("", 204)
    response.headers["HX-Redirect"] = url_for("web.maps", zone=record.id)
    return response


@web_bp.post("/catalogs/import")
@require_group("EDITOR")
def import_yaml() -> Response:
    """Import a YAML definition using the same validator as the form.

    :return: Response indicating the result of the import operation.
    :rtype: Response
    """
    upload = request.files.get("definition")
    if upload is None:
        raise ValueError("Select a YAML file.")
    try:
        definition = yaml.safe_load(upload.read(1024 * 1024))
    except yaml.YAMLError as error:
        raise ValueError("The YAML file is invalid.") from error
    record = save_zone(_database(), definition, _user())
    response = make_response("", 204)
    response.headers["HX-Redirect"] = url_for("web.maps", zone=record.id)
    return response


@web_bp.get("/profile")
@require_group("VIEWER")
def profile() -> str:
    """Display the identity and its persistent preferences.
    
    :return: Rendered profile page.
    :rtype: str
    """
    return _page("profile", "profile")


@web_bp.post("/preferences")
@require_group("VIEWER")
def update_preferences() -> Response:
    """Save only the preferences of the current identity.

    :return: Response indicating the result of the update operation.
    :rtype: Response
    """
    record = preferences(_database(), _user())
    if "navigation" in request.form:
        navigation = request.form["navigation"]
        if navigation not in ("tabs", "workspace"):
            raise ValueError("Choose a navigation variant.")
        record.navigation = navigation
    if "theme" in request.form:
        theme = request.form["theme"]
        if theme not in ("light", "dark", "system"):
            raise ValueError("Unknown theme.")
        record.theme = theme
    _database().add(record)
    _database().commit()
    response = make_response("", 204)
    response.headers["HX-Refresh"] = "true"
    return response


@web_bp.get("/sources")
@require_group("ADMIN")
def sources() -> str:
    """Display the selectable table of existing source zones.

    :return: Rendered sources page.
    :rtype: str
    """
    page = max(request.args.get("page", 1, type=int), 1)
    records = _database() \
        .scalars(_source_query().offset((page - 1) * 50).limit(51)) \
        .all()
    return _page(
        "sources",
        "sources",
        records=records[:50],
        has_next=len(records) > 50,
        page=page,
        query=_query(),
    )


@web_bp.post("/sources/preview")
@require_group("ADMIN")
def source_preview() -> str:
    """Prepare a TOML preview that does not remove any existing entries.

    :return: Rendered source preview fragment.
    :rtype: str
    """
    upload = request.files.get("configuration")
    if upload is None:
        raise ValueError("Select a TOML file.")
    try:
        token, additions = prepare_sources(
            _database(),
            upload.read(2 * 1024 * 1024),
            f"{_user().auth_source}:{_user().id}",
            current_app.secret_key or "",
        )
    except RequestException as error:
        raise ValueError("The upload failed. No source was added.") from error
    return render_template("fragments/source_preview.html", token=token, additions=additions)


@web_bp.post("/sources/apply")
@require_group("ADMIN")
def source_apply() -> Response:
    """Add only the entries present in the validated preview.

    :return: Response indicating the result of the apply operation.
    :rtype: Response
    """
    apply_sources(
        _database(),
        request.form.get("token", ""),
        f"{_user().auth_source}:{_user().id}",
        current_app.secret_key or "",
    )
    response = make_response("", 204)
    response.headers["HX-Redirect"] = url_for("web.sources")
    return response


def _selection() -> list[GeographicZone]:
    """Retrieve the selected geographic zones from the form submission.

    :return: List of selected geographic zones.
    :rtype: list[GeographicZone]
    """
    try:
        identifiers = {int(value) for value in request.form.getlist("source_id")}
    except ValueError as error:
        raise ValueError("Invalid selection") from error
    if not identifiers or len(identifiers) > 50:
        raise ValueError("Select between 1 and 50 sources.")
    records = list(
        _database()
            .scalars(
                select(GeographicZone)
                    .where(GeographicZone.id.in_(identifiers))
                    .with_for_update()
            )
        )
    if len(records) != len(identifiers):
        raise ValueError("The selection has changed. Reload the table.")
    return records


@web_bp.post("/sources/delete-preview")
@require_group("ADMIN")
def delete_preview() -> str:
    """Display the exact selection and dependencies before confirmation.

    :return: Rendered source delete preview fragment.
    :rtype: str
    """
    records = _selection()
    used = set(
        _database()
            .scalars(
                select(GeoForgedItem.geo_zone_id)
                    .where(GeoForgedItem.geo_zone_id.in_([record.id for record in records]))
            )
    )
    return render_template("fragments/source_delete.html", records=records, used=used)


@web_bp.post("/sources/delete")
@require_group("ADMIN")
def delete_sources() -> Response:
    """Delete only the confirmed selection if no version is using it.

    :return: Response indicating the result of the delete operation.
    :rtype: Response
    """
    if request.form.get("confirmed") != "yes":
        raise ValueError("Confirmation is required.")
    records = _selection()
    used = _database() \
            .scalar(
                select(GeoForgedItem.id)
                    .where(GeoForgedItem.geo_zone_id.in_([record.id for record in records]))
                    .limit(1)
            )
    if used is not None:
        raise ValueError(
            "A selected source is used by a version. Deletion blocked."
        )
    for record in records:
        _database().delete(record)
    _database().commit()
    response = make_response("", 204)
    response.headers["HX-Redirect"] = url_for("web.sources")
    return response


@web_bp.get("/administration")
@require_group("ADMIN")
def administration() -> str:
    """Expose the status of accounts and the unlocking of connections.
    
    :return: Rendered administration page fragment.
    :rtype: str
    """
    records = _database().scalars(select(DbUser).order_by(DbUser.username).limit(200)).all()
    return _page("administration", "administration", records=records)


@web_bp.post("/administration/<int:identifier>/unlock")
@require_group("ADMIN")
def unlock_user(identifier: int) -> str:
    """Unlock an account via the existing administration service.

    :param identifier: The ID of the user to unlock.
    :type identifier: int
    :return: Rendered message page fragment indicating the result.
    :rtype: str
    """
    service = UserService(current_app.extensions["georeforge_database"].session)
    if not service.reset_login_lock(identifier):
        abort(404)
    return render_template(_MESSAGE_PAGE, message="Account unlocked.", kind="success")
