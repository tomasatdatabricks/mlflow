import logging
import click
import posixpath

from mlflow.models import Model
from mlflow.models.flavor_backend_registry import get_flavor_backend,\
    get_flavor_backend_for_build_docker
from mlflow.tracking.artifact_utils import _download_artifact_from_uri
from mlflow.utils.file_utils import TempDir
from mlflow.utils import cli_args

_logger = logging.getLogger(__name__)


@click.group("models")
def commands():
    """
    Deploy MLflow models locally.

    To deploy a model associated with a run on a tracking server, set the MLFLOW_TRACKING_URI
    environment variable to the URL of the desired server.
    """
    pass


@commands.command("serve")
@cli_args.MODEL_URI
@cli_args.PORT
@cli_args.HOST
@cli_args.WORKERS
@cli_args.NO_CONDA
@cli_args.INSTALL_MLFLOW
def serve(model_uri, port, host, workers, no_conda=False, install_mlflow=False):
    """
    Serve a model saved with MLflow by launching a webserver on the specified host and port. For
    information about the input data formats accepted by the webserver, see the following
    documentation: https://www.mlflow.org/docs/latest/models.html#model-deployment.
    """
    return _get_flavor_backend(model_uri,
                               no_conda=no_conda,
                               workers=workers,
                               install_mlflow=install_mlflow).serve(model_uri=model_uri, port=port,
                                                                    host=host)


@commands.command("predict")
@cli_args.MODEL_URI
@click.option("--input-path", "-i", default=None,
              help="CSV containing pandas DataFrame to predict against.")
@click.option("--output-path", "-o", default=None,
              help="File to output results to as json file. If not provided, output to stdout.")
@click.option("--content-type", "-t", default="json",
              help="Content type of the input file. Can be one of {'json', 'csv'}.")
@click.option("--json-format", "-j", default="split",
              help="Only applies if the content type is 'json'. Specify how the data is encoded.  "
                   "Can be one of {'split', 'records'} mirroring the behavior of Pandas orient "
                   "attribute. The default is 'split' which expects dict like data: "
                   "{'index' -> [index], 'columns' -> [columns], 'data' -> [values]}, "
                   "where index  is optional. For more information see "
                   "https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.read_json"
                   ".html")
@cli_args.NO_CONDA
@cli_args.INSTALL_MLFLOW
def predict(model_uri, input_path, output_path, content_type, json_format, no_conda,
            install_mlflow):
    """
    Generate predictions in json format using a saved MLflow model. For information about the input
    data formats accepted by this function, see the following documentation:
    https://www.mlflow.org/docs/latest/models.html#model-deployment.
    """
    if content_type == "json" and json_format not in ("split", "records"):
        raise Exception("Unsupported json format '{}'.".format(json_format))
    return _get_flavor_backend(model_uri, no_conda=no_conda,
                               install_mlflow=install_mlflow).predict(model_uri=model_uri,
                                                                      input_path=input_path,
                                                                      output_path=output_path,
                                                                      content_type=content_type,
                                                                      json_format=json_format)


@commands.command("build-docker")
@cli_args.MODEL_URI
@click.option("--name", "-n", default="mlflow-pyfunc-servable",
              help="Name to use for built image")
def build_docker(model_uri, name):
    """
    **EXPERIMENTAL**: Builds a Docker image whose default entrypoint serves the specified MLflow
    model at port 8080 within the container, using the 'python_function' flavor.

    For example, the following command builds a docker image named 'my-image-name' that serves the
    model from run 'some-run-uuid' at run-relative artifact path 'my-model':

    .. code:: bash

        mlflow models build-docker -m "runs:/some-run-uuid/my-model" -n "my-image-name"

    We can then serve the model, exposing it at port 5001 on the host via:

    .. code:: bash

        docker run -p 5001:8080 "my-image-name"

    See https://www.mlflow.org/docs/latest/python_api/mlflow.pyfunc.html for more information on the
    'python_function' flavor.

    This command is experimental and does not guarantee that the arguments nor format of the
    Docker container will remain the same.
    """
    _get_flavor_backend_for_build_docker(model_uri).build_image(model_uri, name, mlflow_home=".")


def _get_flavor_backend_for_build_docker(model_uri, **kwargs):
    with TempDir() as tmp:
        local_path = _download_artifact_from_uri(posixpath.join(model_uri, "MLmodel"),
                                                 output_path=tmp.path())
        model = Model.load(local_path)
    flavor_name, flavor_backend = get_flavor_backend_for_build_docker(model, **kwargs)
    if flavor_backend is None:
        raise Exception("No suitable flavor backend was found for the model.")
    _logger.info("Selected backend for flavor '%s'", flavor_name)
    return flavor_backend


def _get_flavor_backend(model_uri, **kwargs):
    with TempDir() as tmp:
        local_path = _download_artifact_from_uri(posixpath.join(model_uri, "MLmodel"),
                                                 output_path=tmp.path())
        model = Model.load(local_path)
    flavor_name, flavor_backend = get_flavor_backend(model, **kwargs)
    if flavor_backend is None:
        raise Exception("No suitable flavor backend was found for the model.")
    _logger.info("Selected backend for flavor '%s'", flavor_name)
    return flavor_backend
