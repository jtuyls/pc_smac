

from ConfigSpace.configuration_space import ConfigurationSpace
from ConfigSpace.hyperparameters import UniformFloatHyperparameter, \
    CategoricalHyperparameter, Constant

from pc_smac.pc_smac.pipeline_space.node import Node, PreprocessingAlgorithm
from pc_smac.pc_smac.utils.constants import *

class SelectRatesNode(Node):

    def __init__(self):
        self.name = "select_rates"
        self.type = "feature_preprocessor"
        self.hyperparameters = {"alpha": 0.1, "score_func": "chi2"}
        self.algorithm = SelectRates

    def initialize_algorithm(self, hyperparameters):
        hyperparameters = self.initialize_hyperparameters(hyperparameters)
        select_percentile = self.algorithm(alpha=hyperparameters["alpha"],
                                           score_func=hyperparameters["score_func"])

        return (self.get_full_name(), select_percentile)

    def get_hyperparameter_search_space(self, dataset_properties=None):
        return self.algorithm.get_hyperparameter_search_space(dataset_properties=dataset_properties)

    def get_properties(self, dataset_properties=None):
        return self.algorithm.get_properties(dataset_properties=dataset_properties)



class SelectRates(PreprocessingAlgorithm):
    def __init__(self, alpha, mode='fpr',
                 score_func="chi2", random_state=None):
        import sklearn.feature_selection

        self.random_state = random_state  # We don't use this
        self.alpha = float(alpha)

        self.score_func = score_func
        if score_func == "chi2":
            self.score_func_algorithm = sklearn.feature_selection.chi2
        elif score_func == "f_classif":
            self.score_func_algorithm = sklearn.feature_selection.f_classif
        else:
            raise ValueError("score_func must be in ('chi2, 'f_classif'), "
                             "but is: %s" % score_func)

        self.mode = mode

    def get_params(self, deep=True):
        return {
            'alpha': self.alpha,
            'score_func': self.score_func,
            'mode': self.mode,
            'random_state': self.random_state
        }

    def fit(self, X, y):
        import scipy.sparse
        import sklearn.feature_selection

        self.preprocessor = sklearn.feature_selection.GenericUnivariateSelect(
            score_func=self.score_func_algorithm, param=self.alpha, mode=self.mode)

        # Because the pipeline guarantees that each feature is positive,
        # clip all values below zero to zero
        if self.score_func == sklearn.feature_selection.chi2:
            if scipy.sparse.issparse(X):
                X.data[X.data < 0] = 0.0
            else:
                X[X < 0] = 0.0

        self.preprocessor.fit(X, y)
        return self

    def transform(self, X):
        import scipy.sparse
        import sklearn.feature_selection

        # Because the pipeline guarantees that each feature is positive,
        # clip all values below zero to zero
        if self.score_func == sklearn.feature_selection.chi2:
            if scipy.sparse.issparse(X):
                X.data[X.data < 0] = 0.0
            else:
                X[X < 0] = 0.0

        if self.preprocessor is None:
            raise NotImplementedError()
        try:
            Xt = self.preprocessor.transform(X)
        except ValueError as e:
            if "zero-size array to reduction operation maximum which has no " \
                    "identity" in e.message:
                raise ValueError(
                    "%s removed all features." % self.__class__.__name__)
            else:
                raise e

        if Xt.shape[1] == 0:
            raise ValueError(
                "%s removed all features." % self.__class__.__name__)
        return Xt

    @staticmethod
    def get_properties(dataset_properties=None):
        data_type = UNSIGNED_DATA

        if dataset_properties is not None:
            signed = dataset_properties.get('signed')
            if signed is not None:
                data_type = SIGNED_DATA if signed is True else UNSIGNED_DATA

        return {'shortname': 'SR',
                'name': 'Univariate Feature Selection based on rates',
                'handles_regression': False,
                'handles_classification': True,
                'handles_multiclass': True,
                'handles_multilabel': False,
                'is_deterministic': True,
                'input': (SPARSE, DENSE, data_type),
                'output': (INPUT,)}

    @staticmethod
    def get_hyperparameter_search_space(dataset_properties=None):
        alpha = UniformFloatHyperparameter(
            name="alpha", lower=0.01, upper=0.5, default=0.1)

        score_func = CategoricalHyperparameter(
            name="score_func", choices=["chi2", "f_classif"], default="chi2")
        if dataset_properties is not None:
            # Chi2 can handle sparse data, so we respect this
            if 'sparse' in dataset_properties and dataset_properties['sparse']:
                score_func = Constant(
                    name="score_func", value="chi2")

        mode = CategoricalHyperparameter('mode', ['fpr', 'fdr', 'fwe'], 'fpr')

        cs = ConfigurationSpace()
        cs.add_hyperparameter(alpha)
        cs.add_hyperparameter(score_func)
        cs.add_hyperparameter(mode)

        return cs
