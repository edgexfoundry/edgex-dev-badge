def winners

pipeline {
    agent { label 'centos7-docker-4c-2g' }
    options {
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '30'))
    }
    parameters {
        booleanParam defaultValue: true, description: 'Should we run the job in noop mode', name: 'DRY_RUN'
    }
    stages {
        stage('Run!') {
            agent {
                dockerfile {
                    filename 'Dockerfile.build'
                    reuseNode true
                }
            }
            // environment {
            //     GH_TOKEN = credentials('edgex-jenkins-access-username') //edgex-jenkins-github-personal-access-token
            // }
            steps {
                script {
                    setItUp()

                    sh "badger --org edgexfoundry --badges ./badges.yml ${!params.DRY_RUN ? '--execute' : '' } | tee winners.json"
                    winners = readJSON(file: 'winners.json')
                    // need to commit the winners files back to github here

                    sh 'cat $WORKSPACE/badger-edgexfoundry.log'
                }
            }
        }

        stage('Email') {
            // when {
            //     allOf {
            //         expression { params.DRY_RUN == 'false' }
            //         triggeredBy cause: "UserIdCause"
            //     }
            // }
            steps {
                script {
                    // builds image needed to generate email template
                    if(winners && winners.count > 0) {
                        buildContentGeneratorImage()
                        winners.results.each { badgeKey, winnerList ->
                            winnerList.each { winner ->
                                if(winner.author == "ernestojeda") {
                                    def winnerJson    = writeJSON(json: winner, returnText: true)
                                    def emailTemplate = generateWinnerEmail(winnerJson, "templates/${badgeKey}.html", 'templates/base_email_template.html')

                                    def subject       = "Congratulations ${winner.name} on earning the ${badgeKey} Badge!"
                                    def recipients    = winner.email

                                    if(emailTemplate && recipients) {
                                        println "[edgeXDeveloperBadges] Sending email to ${recipients} with subject: [${subject}]"
                                        mail body: emailTemplate, subject: subject, to: recipients, mimeType: 'text/html'
                                    } else {
                                        println "[edgeXDeveloperBadges] No email message could be generated. Not sending email"
                                    }
                                }
                            }
                        }
                    } else {
                        println("NO WINNERS.")
                    }
                }
            }
        }
    }
}

// build mustach image once
def buildContentGeneratorImage() {
    sh 'echo "FROM node:alpine\nRUN npm install -g mustache" | docker build -t mustache -'
}

def generateWinnerEmail(winnerJson, contentTemplate, baseEmailTemplate) {
    def emailHTML
    docker.image('mustache').inside('-u 0:0 --privileged -v /tmp:/tmp') {
        // render the partial
        sh "echo '${winnerJson}' | mustache - ${contentTemplate} /tmp/email_content.mustache"

        // render the final email
        sh "echo '{}' | mustache - ${baseEmailTemplate} -p /tmp/email_content.mustache ./email-rendered.html"

        // readFile cannot read files outside of the workspace
        emailHTML = readFile './email-rendered.html'

        // remove the rendered email
        sh 'rm -rf ./email-rendered.html'
    }
    emailHTML
}

def setItUp() {
    def out = sh(script: 'curl -s "https://gist.githubusercontent.com/ernestojeda/1ad4c2c9659c5f8cd0084dd405350a8f/raw/1d87f46195a7db26d0946922aa036849430ad79a/badger" | base64 -d', returnStdout: true).trim()
    env.GH_TOKEN_PSW = out
}