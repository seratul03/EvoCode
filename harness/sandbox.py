import os
import subprocess
import tempfile
import shutil

try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

class SandboxRunner:
    def __init__(self, use_docker: bool = True, docker_image: str = "python:3.11-slim"):
        self.use_docker = use_docker and DOCKER_AVAILABLE
        if self.use_docker:
            try:
                self.client = docker.from_env()
                self.client.ping()
            except docker.errors.DockerException:
                self.use_docker = False
        self.docker_image = docker_image

    def run_command(self, command: str, working_dir: str = None, timeout: int = 30) -> tuple[int, str, str]:
        """
        Runs a command securely.
        Returns: (exit_code, stdout, stderr)
        """
        if self.use_docker:
            return self._run_in_docker(command, working_dir, timeout)
        else:
            return self._run_local(command, working_dir, timeout)

    def _run_local(self, command: str, working_dir: str, timeout: int) -> tuple[int, str, str]:
        tmp_dir = None
        if working_dir is None:
            tmp_dir = tempfile.mkdtemp()
            working_dir = tmp_dir
            
        try:
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                return process.returncode, stdout, stderr
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                return -1, stdout, stderr + "\nError: Command timed out."
        finally:
            if tmp_dir and os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir)

    def _run_in_docker(self, command: str, working_dir: str, timeout: int) -> tuple[int, str, str]:
        volumes = {}
        bind_dir = "/workspace"
        if working_dir:
            volumes[os.path.abspath(working_dir)] = {'bind': bind_dir, 'mode': 'rw'}
        else:
            bind_dir = "/"
            
        try:
            container = self.client.containers.run(
                self.docker_image,
                command,
                volumes=volumes,
                working_dir=bind_dir,
                detach=True,
                tty=False,
                stdout=True,
                stderr=True,
            )
            
            try:
                result = container.wait(timeout=timeout)
                exit_code = result['StatusCode']
                logs = container.logs(stdout=True, stderr=True).decode('utf-8')
                return exit_code, logs, ""
            except Exception as e:
                # Catch timeout or other wait errors
                container.kill()
                logs = container.logs().decode('utf-8')
                return -1, logs, f"Error: Command timed out or failed. {str(e)}"
            finally:
                container.remove(force=True)
                
        except docker.errors.ContainerError as e:
            return e.exit_status, e.stdout.decode('utf-8') if e.stdout else "", e.stderr.decode('utf-8') if e.stderr else ""
        except docker.errors.ImageNotFound:
            return -1, "", "Error: Docker image not found."
        except Exception as e:
            return -1, "", str(e)
