from python_graphql_client import GraphqlClient

import birdbuddy.queries.auth
from birdbuddy.const import BB_URL


class BirdBuddy:
    def __init__(self):
        self.graphql = GraphqlClient(BB_URL)
        self._me = None
        self._feeders = []

    def login(self, email, password):
        variables = {
            "emailSignInInput": {
                "email": email,
                "password": password,
            }
        }
        data = self.graphql.execute(query=birdbuddy.queries.auth.SignIn, variables=variables)
        # TODO: check for Problem
        self._feeders = data['data']['authEmailSignIn']['me']['feeders']
        return data['data']['authEmailSignIn']

    @property
    def feeders(self):
        return self._feeders
