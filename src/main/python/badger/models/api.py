import datetime
import logging
import os

from github3api import GitHubAPI
from retrying import retry

logger = logging.getLogger(__name__)


class GraphqlRateLimitError(Exception):
    """ GraphQL Rate Limit Error
    """
    pass


class API(GitHubAPI):
    """ use this class if you are at risk of incurring GraphQL ratelimits
        if there is no risk then you can consume GitHubAPI directly without needing
        to subclass it
    """

    def __init__(self, **kwargs):
        """ class constructor
        """
        logger.debug('executing API constructor')
        cabundle = os.getenv('REQUESTS_CA_BUNDLE')
        
        if cabundle:
            super(API, self).__init__(cabundle=cabundle, **kwargs)
        else:
            super(API, self).__init__(**kwargs)
        

    @staticmethod
    def get_client():
        """ return instance of API
        """
        bearer_token = os.getenv('GH_TOKEN_PSW')
        if not bearer_token:
            raise ValueError(
                'environment variable for GH_TOKEN_PSW must be set')
        return API(bearer_token=bearer_token)

    def check_graphqlratelimiterror(exception):
        """ return True if exception is GraphQL Rate Limit Error, False otherwise
        """
        logger.debug(
            f"checking if '{type(exception).__name__}' exception is a GraphqlRateLimitError/TypeError")
        if isinstance(exception, (GraphqlRateLimitError, TypeError)):
            logger.debug(
                'exception is a GraphqlRateLimitError/TypeError - retrying request in 60 seconds')
            return True
        logger.debug(
            f'exception is not a GraphqlRateLimitError/TypeError: {exception}')
        return False

    @retry(retry_on_exception=check_graphqlratelimiterror, wait_fixed=60000, stop_max_attempt_number=60)
    def graphql(self, query):
        """ execute graphql query and return response
        """
        response = self.post('/graphql', json={'query': query})
        if 'errors' in response:
            logger.debug(f'errors detected in graphql response: {response}')
            API.raise_if_ratelimit_error(response['errors'])
        return response

    @staticmethod
    def raise_if_ratelimit_error(errors):
        """ raise GraphqlRateLimitError if error exists in errors
        """
        for error in errors:
            if error.get('type', '') == 'RATE_LIMITED':
                raise GraphqlRateLimitError(error.get('message', ''))

    @staticmethod
    def get_date(days):
        """ return date days ago
        """
        today = datetime.datetime.now()
        target = today - datetime.timedelta(days=days)
        return target.strftime("%Y-%m-%d")

    check_graphqlratelimiterror = staticmethod(check_graphqlratelimiterror)
