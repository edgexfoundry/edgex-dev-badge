//
// Copyright (c) 2021 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//

def winners

pipeline {
    agent { label 'centos7-docker-4c-2g' }
    options {
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '30'))
    }
    parameters {
        string defaultValue: '30', description: 'How far back to search for PRs for a specific repo', name: 'LOOKBACK_WINDOW', trim: true
        booleanParam defaultValue: false, description: 'Do not use lookback window and search ALL PRs', name: 'NO_LOOKBACK'
        booleanParam defaultValue: true, description: 'Should we run the job in noop mode', name: 'DRY_RUN'
    }
    environment {
        ADMIN_RECIPIENTS = 'ernesto.ojeda@intel.com'
        BUILD_FAILURE_NOTIFY_LIST = 'ernesto.ojeda@intel.com'
    }
    stages {
        stage('EdgeX Developer Badges') {
            when {
                expression { shouldBuild() }
            }
            stages {
                // disable DRY_RUN when trigger by croon
                stage('Prep Cron') {
                    when { triggeredBy 'TimerTrigger' }
                    steps {
                        script {
                            env.DRY_RUN = 'false'
                        }
                    }
                }

                stage('Run!') {
                    agent {
                        dockerfile {
                            filename 'Dockerfile.build'
                            reuseNode true
                        }
                    }
                    environment {
                        GH_TOKEN_PSW = credentials('edgex-dev-badges-token')
                    }
                    steps {
                        script {
                            def bargerArgs = [
                                '--org edgexfoundry',
                                '--badges ./badges.yml'
                            ]

                            if(env.NO_LOOKBACK == 'true') {
                                bargerArgs << '--no-lookback'
                            } else {
                                // default is 30 days, but maybe someone might want to override?
                                if(env.LOOKBACK_WINDOW) {
                                    // normalize in case bad input
                                    def lookback = env.LOOKBACK_WINDOW == '' || env.LOOKBACK_WINDOW == '0' ? '30' : env.LOOKBACK_WINDOW

                                    bargerArgs << "--lookback ${lookback}"
                                }
                            }

                            if(env.DRY_RUN == 'false') {
                                bargerArgs << '--execute'
                            }

                            def badgerCommand = "badger ${bargerArgs.join(' ')}"
                            println "[edgeXDeveloperBadges] Running badger command: ${badgerCommand}"

                            sh badgerCommand
                            winners = readJSON(file: 'winners.json')
                            archiveArtifacts allowEmptyArchive: true, artifacts: 'badger-edgexfoundry.log'
                        }
                    }
                }

                stage('Email') {
                    when {
                        anyOf {
                            triggeredBy "UserIdCause"
                            triggeredBy 'TimerTrigger'
                        }
                    }
                    steps {
                        script {
                            // builds image needed to generate email template
                            if(winners && winners.count > 0) {
                                buildContentGeneratorImage()

                                sendWinnerEmails(winners)
                                sendAdminEmail(winners, env.ADMIN_RECIPIENTS)
                            } else {
                                println("[edgeXDeveloperBadges] NO BADGES ENABLED OR NO WINNERS FOUND.")
                            }
                        }
                    }
                }

                stage('Commit Changes') {
                    when {
                        expression { env.DRY_RUN == 'false' }
                    }
                    steps {
                        sh '''
                        git status
                        if ! git diff-index --quiet HEAD --; then
                            echo "[edgeXDeveloperBadges] We have detected there are changes to commit."
                            git config --global user.email "jenkins@edgexfoundry.org"
                            git config --global user.name "EdgeX Jenkins"
                            git add badges/*
                            git commit -s -m "chore(badge-recipients): Jenkins updated badge recipients"
                            git branch update-chore
                            git checkout "$GIT_BRANCH"
                            git merge update-chore
                            sudo chmod -R ug+w .git/*
                        else
                            echo "Nothing to commit"
                        fi
                        '''
                        sshagent(credentials: ['edgex-jenkins-ssh']) {
                            retry(3) {
                                sh 'git push origin "$GIT_BRANCH"'
                            }
                        }
                    }
                }
            }
        }
    }
    post {
        failure {
            script {
                currentBuild.result = 'FAILED'
                // only send email when on a release stream branch i.e. main, hanoi, ireland, etc.
                if(edgex.isReleaseStream()) {
                    edgeXEmail(emailTo: env.BUILD_FAILURE_NOTIFY_LIST)
                }
            }
        }
        always {
            edgeXInfraPublish()
        }
    }
}

// build mustach image once
def buildContentGeneratorImage() {
    sh 'echo "FROM node:alpine\nRUN npm install -g mustache" | docker build -t mustache -'
}

// TODO: migrate this to python
def generateWinnerEmail(finalWinnersFile, author, displayName, contentTemplate, baseEmailTemplate) {
    def emailHTML
    docker.image('mustache').inside('-u 0:0 --privileged -v /tmp:/tmp') {
        sh "rm -f ./email-rendered-${author}.html" // paranoia

        // render the partial
        sh "rm -f /tmp/email_content.mustache && cat '${finalWinnersFile}' | mustache - ${contentTemplate} /tmp/email_content.mustache"

        // render the final email
        sh "echo '{\"badge_name\": \"${displayName}\"}' | mustache - ${baseEmailTemplate} -p /tmp/email_content.mustache ./email-rendered-${author}.html"

        // readFile cannot read files outside of the workspace
        emailHTML = readFile "./email-rendered-${author}.html"

        if(env.DRY_RUN == 'true') {
            archiveArtifacts allowEmptyArchive: true, artifacts: "email-rendered-${author}.html"
        }
    }
    emailHTML
}

def sendWinnerEmails(winners) {
    winners.results.each { badgeKey, winnerList ->
        badgeDetails = winners.badge_details[badgeKey]
        
        winnerList.each { winner ->
            winner.first_name = winner.name.split(' ')[0]
            winner.image_url = badgeDetails.image_url
            winner.download_url = badgeDetails.download_url

            def finalWinners = './winners-final.json'
            writeJSON(json: winner, file: finalWinners)
            def emailTemplate = generateWinnerEmail(finalWinners, winner.author, badgeDetails.display, "templates/${badgeKey}.html", 'templates/base_email_template.html')

            def subject       = "Congratulations ${winner.name} on earning the ${badgeDetails.display} Badge!"
            def recipients    = winner.email

            if(emailTemplate && recipients) {
                println "[edgeXDeveloperBadges] Sending email to ${recipients} with subject: [${subject}]"
                
                if(env.DRY_RUN == 'false') {
                    mail body: emailTemplate, subject: subject, to: recipients, mimeType: 'text/html'
                } else {
                    println('[edgeXDeveloperBadges] DRY_RUN...not sending email. Check artifacts.')
                }
            } else {
                println "[edgeXDeveloperBadges] No email message could be generated. Not sending email"
            }
        }
    }
}

def sendAdminEmail(winners, recipients) {
    def winnerCount = 0
    def adminEmailBody = "<h1>EdgeX Badge Winners Awarded</h1><p>The following users were awarded badges today. See more info here: <a href=\"${env.BUILD_URL}\">${env.BUILD_URL}</a></p>"
    adminEmailBody += "<ul>"
    winners.results.each { badgeKey, winnerList ->
        badgeDetails = winners.badge_details[badgeKey]

        winnerList.each { winner ->
            adminEmailBody += "<li><a href=\"http://github.com/${winner.author}\" target=\"_blank\">${winner.name}</a> [<a href=\"mailto:${winner.email}\">${winner.email}</a>]</li>"
            winnerCount++
        }
    }
    adminEmailBody += "</ul>"
    adminEmailBody += "<p>For further info please email the DevOps WG email or visit the <a href=\"https://edgexfoundry.slack.com/archives/CE46S51DX\" target=\"_blank\">#devops</a> slack channel</p>"

    if(env.DRY_RUN == 'false') {
        mail body: adminEmailBody, subject: "[${winnerCount}] EdgeX Badge Winners Awarded", to: recipients, mimeType: 'text/html'
    } else {
        println('[edgeXDeveloperBadges] DRY_RUN...not admin sending email. Check artifacts.')
        writeFile(file: 'admin_email.html', text: adminEmailBody)
        archiveArtifacts allowEmptyArchive: true, artifacts: 'admin_email.html'
    }
}

def shouldBuild() {
    def commitMessage = edgex.getCommitMessage(env.GIT_COMMIT)
    commitMessage =~ /^chore\(badge-recipients\)/ ? false : true
}