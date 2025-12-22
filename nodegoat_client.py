"""
nodegoat API client for Stephanos project.

Provides methods for querying and updating data in nodegoat using OAuth 2.0.
Based on nodegoat REST API documentation.
"""
import json
import requests
from typing import Optional, Dict, List, Any
from config import NODEGOAT_URL, NODEGOAT_TOKEN, NODEGOAT_PROJECT_ID


class NodegoatClient:
    """Client for interacting with nodegoat REST API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        project_id: Optional[str] = None,
    ):
        """
        Initialize nodegoat client.

        Args:
            base_url: nodegoat instance URL (default: from config)
            token: Bearer token for authentication (default: from config)
            project_id: Default project ID (default: from config)
        """
        self.base_url = (base_url or NODEGOAT_URL).rstrip("/")
        self.token = token or NODEGOAT_TOKEN
        self.project_id = project_id or NODEGOAT_PROJECT_ID

        if not self.token:
            raise ValueError(
                "nodegoat token not configured. "
                "Add token to stephanos.ini or pass to constructor."
            )

    def _request(
        self,
        method: str,
        path: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Make authenticated request to nodegoat API.

        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE)
            path: API path (without base URL)
            data: JSON body for POST/PUT/PATCH requests
            params: Query parameters

        Returns:
            JSON response as dictionary

        Raises:
            requests.HTTPError: On HTTP error responses
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=data,
            params=params,
        )

        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            # Try to include response body in error message
            try:
                error_detail = response.json()
                print(f"Error response: {json.dumps(error_detail, indent=2)}")
            except:
                print(f"Error response: {response.text}")
            raise e

        return response.json()

    def get_openapi_spec(self, project_id: Optional[str] = None) -> Dict:
        """
        Get OpenAPI specification for the API.

        Args:
            project_id: Project ID (default: use configured default)

        Returns:
            OpenAPI specification as dictionary
        """
        pid = project_id or self.project_id
        path = f"/project/{pid}/.openapi" if pid else "/.openapi"
        return self._request("GET", path)

    def query_data(
        self,
        type_id: int,
        project_id: Optional[str] = None,
        object_id: Optional[int] = None,
        search: Optional[str] = None,
        filter_json: Optional[Dict] = None,
        scope_json: Optional[Dict] = None,
        output: str = "default",
        order: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Query data from nodegoat.

        Args:
            type_id: Object Type ID to query
            project_id: Project ID (default: use configured default)
            object_id: Specific object ID to retrieve
            search: Quick search value
            filter_json: JSON-formatted filter (dict)
            scope_json: JSON-formatted scope (dict)
            output: Output format (raw|default|template)
            order: Sort order (e.g., "name:ASC")
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            API response with data
        """
        pid = project_id or self.project_id
        path = f"/project/{pid}/data/type/{type_id}/object" if pid else f"/data/type/{type_id}/object"

        params = {}
        if object_id:
            params["object_id"] = object_id
        if search:
            params["search"] = search
        if filter_json:
            params["filter"] = json.dumps(filter_json)
        if scope_json:
            params["scope"] = json.dumps(scope_json)
        if output != "default":
            params["output"] = output
        if order:
            params["order"] = order
        if limit:
            params["limit"] = limit
        if offset:
            params["offset"] = offset

        return self._request("GET", path, params=params)

    def query_model(
        self,
        type_id: Optional[int] = None,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Query the data model (Type definitions).

        Args:
            type_id: Specific Type ID (omit to list all Types)
            project_id: Project ID (default: use configured default)

        Returns:
            Model definition(s)
        """
        pid = project_id or self.project_id
        if type_id:
            path = f"/project/{pid}/model/type/{type_id}" if pid else f"/model/type/{type_id}"
        else:
            path = f"/project/{pid}/model/type" if pid else "/model/type"

        return self._request("GET", path)

    def store_data(
        self,
        type_id: int,
        data: Dict[str, Any],
        method: str = "PUT",
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Store (create/update/delete) data in nodegoat.

        Args:
            type_id: Object Type ID
            data: Data to store. Format depends on method:
                PUT: {"add": [...], "update": {...}}
                PATCH: {"object": {...}, "object_definitions": [...], ...}
                DELETE: {object_id: true, ...}
            method: HTTP method (PUT, PATCH, DELETE)
            project_id: Project ID (default: use configured default)

        Returns:
            API response with added/updated/deleted IDs
        """
        pid = project_id or self.project_id
        path = f"/project/{pid}/data/type/{type_id}/object" if pid else f"/data/type/{type_id}/object"

        return self._request(method, path, data=data)

    def create_objects(
        self,
        type_id: int,
        objects: List[Dict],
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create new objects in nodegoat.

        Args:
            type_id: Object Type ID
            objects: List of objects to create
            project_id: Project ID (default: use configured default)

        Returns:
            API response with created object IDs
        """
        return self.store_data(type_id, {"add": objects}, method="PUT", project_id=project_id)

    def update_objects(
        self,
        type_id: int,
        updates: Dict[int, Dict],
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update existing objects in nodegoat.

        Args:
            type_id: Object Type ID
            updates: Dictionary mapping object IDs to update data
            project_id: Project ID (default: use configured default)

        Returns:
            API response with updated object IDs
        """
        return self.store_data(type_id, {"update": updates}, method="PUT", project_id=project_id)

    def patch_object(
        self,
        type_id: int,
        object_data: Dict,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Partially update a single object (only specified fields).

        Args:
            type_id: Object Type ID
            object_data: Object data (only fields to update)
            project_id: Project ID (default: use configured default)

        Returns:
            API response
        """
        return self.store_data(type_id, object_data, method="PATCH", project_id=project_id)

    def delete_objects(
        self,
        type_id: int,
        object_ids: List[int],
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Delete objects from nodegoat.

        Args:
            type_id: Object Type ID
            object_ids: List of object IDs to delete
            project_id: Project ID (default: use configured default)

        Returns:
            API response with deleted object IDs
        """
        delete_data = {obj_id: True for obj_id in object_ids}
        return self.store_data(type_id, delete_data, method="DELETE", project_id=project_id)
