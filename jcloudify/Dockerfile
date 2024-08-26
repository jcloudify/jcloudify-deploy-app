FROM public.ecr.aws/lambda/python:3.9

RUN yum -y install \
    curl \
    unzip \
    && yum clean all

RUN curl -Lo /tmp/sam-installation.zip https://github.com/aws/aws-sam-cli/releases/latest/download/aws-sam-cli-linux-x86_64.zip \
    && unzip /tmp/sam-installation.zip -d /tmp/sam-installation \
    && /tmp/sam-installation/install \
    && rm -rf /tmp/sam-installation /tmp/sam-installation.zip

RUN curl -Lo /tmp/openjdk-21_linux-x64_bin.tar.gz https://download.oracle.com/java/21/latest/jdk-21_linux-x64_bin.tar.gz \
    && mkdir -p /opt/java-21 \
    && python3.9 -c "import tarfile; tarfile.open('/tmp/openjdk-21_linux-x64_bin.tar.gz', 'r:gz').extractall('/opt/java-21')" \
    && rm /tmp/openjdk-21_linux-x64_bin.tar.gz \
    && cd /opt/java-21 \
    && mv jdk-21* java-21-openjdk

ENV JAVA_HOME /opt/java-21/java-21-openjdk
ENV PATH $JAVA_HOME/bin:$PATH

RUN mkdir -p /tmp/.gradle
RUN export GRADLE_USER_HOME=/tmp/.gradle
ENV GRADLE_USER_HOME=/tmp/.gradle

COPY requirements.txt ./
RUN python3.9 -m pip install -r requirements.txt -t .

COPY app.py ./

CMD ["app.lambda_handler"]
