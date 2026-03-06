from typing import Any, Generic, TypeVar, cast, overload
from uuid import UUID

from postgrest import CountMethod
from pydantic import BaseModel
from supabase import Client

T = TypeVar("T", bound=BaseModel)
U = TypeVar("U", bound=BaseModel)


class BaseRepository(Generic[T]):
    """
    Base repository providing common CRUD operations.
    
    This generic repository class serves as a foundation for all domain-specific repositories,
    providing standard database operations through the Supabase client. Subclasses inherit
    type-safe CRUD methods and only need to implement domain-specific queries.
    
    Type Parameters:
        T: A Pydantic BaseModel subclass that represents the data model for this repository.
    """

    def __init__(self, client: Client, table_name: str, model: type[T]) -> None:
        """
        Initialize the repository with database connection and model configuration.

        Args:
            client (Client): The Supabase client instance for database operations.
            table_name (str): The name of the database table this repository manages.
            model (type[T]): The Pydantic model class used to validate and structure response data.
        """
        self.client = client
        self.table = table_name
        self.model = model

    @overload
    def _to_model(self, data: Any, model: None = None) -> T: ...

    @overload
    def _to_model(self, data: Any, model: type[U]) -> U: ...

    def _to_model(self, data: Any, model: type[U] | None = None) -> T | U:
        """
        Convert raw database response data into a validated model instance.

        Args:
            data (Any): Raw data from the database response, expected to be a dictionary.
            model (type[U] | None): Optional override model class to use for validation. 
            Defaults to the repository's model.

        Returns:
            T | U: A validated instance of the specified or default model type.
        """
        model_to_use = model if model else self.model
        return model_to_use.model_validate(cast(dict[str, Any], data))

    @overload
    def _to_model_list(self, data: list[Any], model: None = None) -> list[T]: ...

    @overload
    def _to_model_list(self, data: list[Any], model: type[U]) -> list[U]: ...

    def _to_model_list(self, data: list[Any], model: type[U] | None = None) -> list[T] | list[U]:
        """
        Convert a list of raw database records into validated model instances.

        Args:
            data (list[Any]): List of raw records from the database response.
            model (type[T] | None): Optional override model class to use for validation. 
            Defaults to the repository's model.

        Returns:
            list[T]: A list of validated model instances.
        """
        if model is not None:
            return [model.model_validate(cast(dict[str, Any], row)) for row in data]
        return [self.model.model_validate(cast(dict[str, Any], row)) for row in data]

    def get_by_id(self, id: UUID) -> T | None:
        """
        Retrieve a single record by its unique identifier.

        Args:
            id (UUID): The unique identifier of the record to retrieve.

        Returns:
            T | None: The model instance if found, None if no record exists with the given ID.
        """
        response = (
            self.client.table(self.table)
            .select("*")
            .eq("id", str(id))
            .single()
            .execute()
        )
        return self._to_model(response.data) if response.data else None

    def get_all(self, limit: int = 100, offset: int = 0) -> list[T]:
        """
        Retrieve all records from the table with pagination support.

        Args:
            limit (int): Maximum number of records to return. Defaults to 100.
            offset (int): Number of records to skip before starting to return results. Defaults to 0.

        Returns:
            list[T]: A list of model instances. Returns an empty list if no records are found.
        """
        response = (
            self.client.table(self.table)
            .select("*")
            .range(offset, offset + limit - 1)
            .execute()
        )
        return self._to_model_list(response.data or [])

    def create(self, data: dict[str, Any]) -> T:
        """
        Create a new record in the table.

        Args:
            data (dict[str, Any]): A dictionary containing the field values for the new record.

        Returns:
            T: The newly created model instance with all database-generated fields populated.
        """
        response = (
            self.client.table(self.table)
            .insert(data)
            .execute()
        )
        return self._to_model(response.data[0])

    def update(self, id: UUID, data: dict[str, Any]) -> T | None:
        """
        Update an existing record by its unique identifier.

        Args:
            id (UUID): The unique identifier of the record to update.
            data (dict[str, Any]): A dictionary containing the fields and values to update.

        Returns:
            T | None: The updated model instance if successful, None if the record was not found.
        """
        response = (
            self.client.table(self.table)
            .update(data)
            .eq("id", str(id))
            .execute()
        )
        return self._to_model(response.data[0]) if response.data else None

    def delete(self, id: UUID) -> bool:
        """
        Delete a record by its unique identifier.

        Args:
            id (UUID): The unique identifier of the record to delete.

        Returns:
            bool: True if the record was successfully deleted, False if no record was found.
        """
        response = (
            self.client.table(self.table)
            .delete()
            .eq("id", str(id))
            .execute()
        )
        return len(response.data) > 0

    def count(self) -> int:
        """
        Count the total number of records in the table.

        Returns:
            int: The total number of records. Returns 0 if the table is empty.
        """
        response = (
            self.client.table(self.table)
            .select("*", count=CountMethod.exact)
            .execute()
        )
        return response.count or 0
