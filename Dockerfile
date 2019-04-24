FROM lambci/lambda:build-python3.6

COPY setup.py setup.py
COPY rio_viz/ rio_viz/
COPY MANIFEST.in MANIFEST.in

RUN pip3 install pip cython==0.28 numpy -U

# Install dependencies
RUN pip3 install . -U

WORKDIR /local