from mwrogue.esports_client import EsportsClient
from mwrogue.auth_credentials import AuthCredentials

class LeaguepediaSite:
    """A ghost loaded class that handles Leaguepedia connection and some caching.

    Full documentation: https://lol.fandom.com/Help:API_Documentation
    """

    def __init__(self, limit=500):
        self._site = None
        self.limit = limit

    @property
    def site(self):
        if not self._site:
            self._load_site()

        return self._site

    def _load_site(self):
        user_agent = "MiApp/1.0 (tuemail@dominio.com)"
        credentials = AuthCredentials(username='Ey3z1@Bot1', password='q3hbmi6i0tenkgj0o22nd3krbj88cq82')
        self._site = EsportsClient('lol', credentials=credentials, clients_useragent=user_agent)

    def query(self, **kwargs) -> list:
        """Issues a cargo query to leaguepedia.

        Params are usually:
            tables, join_on, fields, order_by, where

        Returns:
            List of rows from the query.
        """
        result = []

        # We check if we hit the API limit
        while len(result) % self.limit == 0:
            result.extend(
                self.site.cargo_client.query(
                    limit=self.limit, offset=len(result), **kwargs
                )
            )

            # If the cargoquery is empty, we stop the loop
            if not result:
                break

        return result


# Ghost loaded instance shared by all other classes
leaguepedia = LeaguepediaSite()
