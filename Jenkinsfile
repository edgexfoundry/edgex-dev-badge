def winners

pipeline {
    agent { label 'centos7-docker-4c-2g' }
    stages {
        stage('Run!') {
            agent {
                dockerfile {
                    filename 'Dockerfile.build'
                    args '--entrypoint='
                    reuseNode true
                }
            }
            environment {
                GH_TOKEN = credentials('edgex-jenkins-access-username') //edgex-jenkins-github-personal-access-token
            }
            steps {
                script {
                    sh 'python badger.py | tee winners.json'
                    winners = readJSON(file: './winners.json')
                }
            }
        }

        stage('Email') {
            steps {
                script {
                    emailTemplate = generateEmail(winners)

                    // def buildStatus = currentBuild.result == null ? "SUCCESS" : currentBuild.result
                    // def subject     = config.subject ?: "[${buildStatus}] ${env.JOB_NAME} Build #${env.BUILD_NUMBER}"
                    // def recipients  = config.emailTo

                    // println "[edgeXEmailHelper] config: ${config}"

                    // if(renderedEmailTemplate && recipients) {
                    //     mail body: renderedEmailTemplate, subject: subject, to: recipients, mimeType: 'text/html'
                    // } else {
                    //     println "[edgeXEmailHelper] No email message could be generated. Not sending email"
                    // }
                }
            }
        }
    }
}

def generateEmail(winners) {
    println("Winners: ${winners}")
    return "email"
}