# The self-hosted reports: the official server image with this project copied in. Pinned by digest,
# and at the same version as the CLI in the Makefile -- see evidence.config.yaml.
FROM evidencedev/serve:0.10.1@sha256:6d4abc5bf438ad0955eaba45e1faf9f8f86e681fd038cbf11f975dcdeb29550b
COPY --chown=evidence:evidence . /project
