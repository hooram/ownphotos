FROM ubuntu:16.04
MAINTAINER ViViDboarder <vividboarder@gmail.com>

ENV MAPZEN_API_KEY mapzen-XXXX
ENV MAPBOX_API_KEY mapbox-XXXX
ENV ALLOWED_HOSTS=*

RUN apt-get update && \
    env DEBIAN_FRONTEND=noninteractive apt-get install -y tzdata && \
    apt-get install -y \
    libsm6 \
    libboost-all-dev \
    libglib2.0-0 \
    libxrender-dev \ 
    python3-tk \
    libffi-dev \
    libssl-dev \
    python3 \
    python3-pip \
    python3-venv \
    wget \
    curl \
    nginx 

RUN apt-get install -y libopenblas-dev liblapack-dev

# Create venv
RUN python3 -m venv /venv && /venv/bin/pip install wheel

# Build and install dlib
RUN apt-get update && \
    apt-get install -y cmake git && \
    git clone https://github.com/davisking/dlib.git && \
    mkdir /dlib/build && \
    cd /dlib/build && \
    cmake .. -DDLIB_USE_CUDA=0 -DUSE_AVX_INSTRUCTIONS=0 && \
    cmake --build . && \
    cd /dlib && \
    /venv/bin/python setup.py install --no USE_AVX_INSTRUCTIONS --no DLIB_USE_CUDA 

RUN /venv/bin/pip install cython

RUN /venv/bin/pip install https://download.pytorch.org/whl/cpu/torch-0.4.1-cp35-cp35m-linux_x86_64.whl && /venv/bin/pip install torchvision

RUN mkdir /code
WORKDIR /code
COPY requirements.txt /code/

RUN /venv/bin/pip install spacy==2.0.16 && /venv/bin/python -m spacy download en_core_web_sm

# Work around broken pyocclient setup.py
# This commit is 5 commits after v0.4 and fixes the UnicodeDecodeError during installation
RUN /venv/bin/pip install https://github.com/owncloud/pyocclient/archive/78984391ded8b72dd0742c67968310a469b15063.zip 

RUN /venv/bin/pip install -r requirements.txt

WORKDIR /code/api/places365
RUN wget https://s3.eu-central-1.amazonaws.com/ownphotos-deploy/places365_model.tar.gz
RUN tar xf places365_model.tar.gz

WORKDIR /code/api/im2txt
RUN wget https://s3.eu-central-1.amazonaws.com/ownphotos-deploy/im2txt_model.tar.gz
RUN tar xf im2txt_model.tar.gz
RUN wget https://s3.eu-central-1.amazonaws.com/ownphotos-deploy/im2txt_data.tar.gz
RUN tar xf im2txt_data.tar.gz


WORKDIR /
RUN curl -sL https://deb.nodesource.com/setup_8.x -o nodesource_setup.sh 
RUN bash nodesource_setup.sh
RUN apt-get install -y nodejs

WORKDIR /code
RUN git clone https://github.com/hooram/ownphotos-frontend.git
WORKDIR /code/ownphotos-frontend
RUN git pull origin dev && git checkout dev
RUN mv /code/ownphotos-frontend/src/api_client/apiClientDeploy.js /code/ownphotos-frontend/src/api_client/apiClient.js
RUN npm install
RUN npm install -g serve

RUN apt-get remove --purge -y cmake git && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

VOLUME /data

# Application admin creds
ENV ADMIN_EMAIL admin@dot.com
ENV ADMIN_USERNAME admin
ENV ADMIN_PASSWORD changeme

# Django key. CHANGEME
ENV SECRET_KEY supersecretkey
# Until we serve media files properly (django dev server doesn't serve media files with with debug=false)
ENV DEBUG true 

# Database connection info
ENV DB_BACKEND postgresql
ENV DB_NAME ownphotos
ENV DB_USER ownphotos
ENV DB_PASS ownphotos
ENV DB_HOST database
ENV DB_PORT 5432

ENV BACKEND_HOST localhost
ENV FRONTEND_HOST localhost

# REDIS location
ENV REDIS_HOST redis
ENV REDIS_PORT 11211

# Timezone
ENV TIME_ZONE UTC

EXPOSE 80
EXPOSE 3000
EXPOSE 5000

COPY . /code

RUN mv /code/config_docker.py /code/config.py

WORKDIR /code

ENTRYPOINT ./entrypoint.sh
